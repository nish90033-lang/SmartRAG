from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
from typing import Optional

from ingest import ingest_document
from retrieval import retrieve
from llm import generate_answer, fallback_answer
from ecc_auth import get_public_jwk, get_public_key_pem   # ← ECC public key export
from database import (
    get_user_from_token, save_document, save_chunks,
    get_user_chunks, save_chat, get_user_chat_history,
    check_duplicate, get_user_documents,
    create_user, login_user, create_token
)

app = FastAPI(title="SmartRAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Pydantic models ───────────────────────────────────────────────────────────

class AuthRequest(BaseModel):
    email:    str
    password: str


class QueryRequest(BaseModel):
    question: str
    use_llm:  bool                = True
    doc_id:   Optional[str]       = None   # legacy single-doc
    doc_ids:  Optional[list[str]] = None   # multi-doc selection


class TextUploadRequest(BaseModel):
    text:     str
    doc_name: str = "Untitled Text Document"


# ── Auth helper ───────────────────────────────────────────────────────────────

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "")
    user  = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/auth/public-key")
def public_key():
    """
    Return the ECC P-256 public key in two formats:

    • jwk — JSON Web Key object (standard, machine-readable)
      Use this to verify SmartRAG JWTs from any external service or auditor.

    • pem — PEM-encoded public key (human-readable)
      Paste into jwt.io or any JWT debugger to inspect tokens.

    The private key never leaves the server.
    Tokens are signed with ES256 (P-256 ECDSA) — exposing this public key
    cannot allow anyone to forge new tokens.
    """
    return {
        "algorithm": "ES256",
        "curve":     "P-256",
        "jwk":       get_public_jwk(),
        "pem":       get_public_key_pem(),
    }


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"status": "SmartRAG is running"}


@app.options("/{full_path:path}")
async def preflight_handler():
    return {"message": "Preflight OK"}


@app.post("/auth/signup")
def signup(request: AuthRequest):
    user = create_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=400, detail="Email already registered.")
    token = create_token(user["id"], user["email"])
    return {"token": token, "user": user}


@app.post("/auth/login")
def login(request: AuthRequest):
    user = login_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_token(user["id"], user["email"])
    return {"token": token, "user": user}


@app.post("/upload")
async def upload_document(
    file:          UploadFile     = File(...),
    authorization: Optional[str] = Header(None)
):
    user    = get_current_user(authorization)
    user_id = str(user["id"])

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    result = ingest_document(file_path)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    if check_duplicate(user_id, result["doc_hash"]):
        raise HTTPException(status_code=400, detail="You have already uploaded this document.")

    save_document(
        user_id     = user_id,
        doc_id      = result["doc_id"],
        doc_hash    = result["doc_hash"],
        trust_score = result["trust_score"],
        chunk_count = result["chunk_count"],
        filename    = file.filename
    )
    save_chunks(user_id, result["doc_id"], result["chunks"], result["trust_score"])

    return {
        "message":        "Document uploaded and indexed successfully.",
        "doc_id":         result["doc_id"],
        "trust_score":    result["trust_score"],
        "chunk_count":    result["chunk_count"],
        "patterns_found": result.get("patterns_found", 0),
        "source_type":    "pdf",
    }


@app.post("/upload-text")
async def upload_text(
    request:       TextUploadRequest,
    authorization: Optional[str] = Header(None)
):
    user    = get_current_user(authorization)
    user_id = str(user["id"])

    result = ingest_document(request.text)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    if check_duplicate(user_id, result["doc_hash"]):
        raise HTTPException(status_code=400, detail="You have already uploaded this content.")

    save_document(
        user_id     = user_id,
        doc_id      = result["doc_id"],
        doc_hash    = result["doc_hash"],
        trust_score = result["trust_score"],
        chunk_count = result["chunk_count"],
        filename    = request.doc_name,
    )
    save_chunks(user_id, result["doc_id"], result["chunks"], result["trust_score"])

    return {
        "message":        f"Text ingested successfully. {result['chunk_count']} chunks indexed.",
        "doc_id":         result["doc_id"],
        "doc_name":       request.doc_name,
        "trust_score":    result["trust_score"],
        "chunk_count":    result["chunk_count"],
        "patterns_found": result.get("patterns_found", 0),
        "source_type":    "text",
    }


@app.post("/query")
def query_document(
    request:       QueryRequest,
    authorization: Optional[str] = Header(None)
):
    user    = get_current_user(authorization)
    user_id = str(user["id"])

    user_chunks = get_user_chunks(user_id)

    # Document filtering
    if request.doc_ids:
        user_chunks = [c for c in user_chunks if c["doc_id"] in request.doc_ids]
    elif request.doc_id:
        user_chunks = [c for c in user_chunks if c["doc_id"] == request.doc_id]
    # else: both None → search ALL user documents

    if not user_chunks:
        raise HTTPException(status_code=400, detail="No documents found. Please upload a PDF or paste text first.")

    # Pass chunk dicts directly — retrieval.py expects list[dict] with
    # keys: content, doc_id, trust_score, chunk_index
    retrieval_result = retrieve(request.question, user_chunks)

    if not retrieval_result["answerable"]:
        answer = retrieval_result.get("blocked_reason") or \
                 "I don't have enough information in your documents to answer that."
        save_chat(user_id, request.question, answer, False)
        return {"answer": answer, "answerable": False, "sources": []}

    # Extract plain text for LLM
    top_chunks  = retrieval_result["chunks"]
    chunk_texts = [c["content"] for c in top_chunks]

    if request.use_llm:
        answer = generate_answer(request.question, chunk_texts)
    else:
        answer = fallback_answer(chunk_texts)

    save_chat(user_id, request.question, answer, True)

    # Build sources from reranked chunk dicts
    sources = [
        {
            "chunk_index":     c.get("chunk_index", i + 1),
            "doc_id":          c.get("doc_id", "unknown"),
            "trust_score":     c.get("trust_score", 100.0),
            "relevance_score": c.get("relevance_score", 0.0),
            "excerpt":         c.get("content", "")[:200] + "..."
        }
        for i, c in enumerate(top_chunks)
    ]

    sources.sort(key=lambda x: -x["relevance_score"])

    return {"answer": answer, "answerable": True, "sources": sources}


@app.get("/documents")
def get_documents(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    docs = get_user_documents(str(user["id"]))
    return {"documents": docs}


@app.get("/history")
def get_history(authorization: Optional[str] = Header(None)):
    user    = get_current_user(authorization)
    history = get_user_chat_history(str(user["id"]))
    return {"history": history}


@app.delete("/history")
def clear_history(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return {"message": "History cleared."}