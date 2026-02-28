from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
from typing import Optional

from ingest import ingest_document
from retrieval import retrieve
from llm import generate_answer, fallback_answer
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

class AuthRequest(BaseModel):
    email: str
    password: str

class QueryRequest(BaseModel):
    question: str
    use_llm: bool = True
    doc_id: Optional[str] = None

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "")
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

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
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None)
):
    user = get_current_user(authorization)
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
        user_id=user_id,
        doc_id=result["doc_id"],
        doc_hash=result["doc_hash"],
        trust_score=result["trust_score"],
        chunk_count=result["chunk_count"],
        filename=file.filename
    )
    save_chunks(user_id, result["doc_id"], result["chunks"], result["trust_score"])

    return {
        "message": "Document uploaded and indexed successfully.",
        "doc_id": result["doc_id"],
        "trust_score": result["trust_score"],
        "chunk_count": result["chunk_count"]
    }

@app.post("/query")
def query_document(
    request: QueryRequest,
    authorization: Optional[str] = Header(None)
):
    user = get_current_user(authorization)
    user_id = str(user["id"])

    user_chunks = get_user_chunks(user_id)

    if request.doc_id:
        user_chunks = [c for c in user_chunks if c["doc_id"] == request.doc_id]

    if not user_chunks:
        raise HTTPException(status_code=400, detail="No documents found. Please upload a PDF first.")

    chunks = [c["content"] for c in user_chunks]
    metadatas = [
        {
            "doc_id": c["doc_id"],
            "trust": c["trust_score"],
            "chunk_index": c["chunk_index"]
        }
        for c in user_chunks
    ]

    retrieval_result = retrieve(request.question, chunks, metadatas)

    if not retrieval_result["answerable"]:
        answer = "I don't have enough information in your documents to answer that."
        save_chat(user_id, request.question, answer, False)
        return {"answer": answer, "answerable": False, "sources": []}

    if request.use_llm:
        answer = generate_answer(request.question, retrieval_result["chunks"])
    else:
        answer = fallback_answer(retrieval_result["chunks"])

    save_chat(user_id, request.question, answer, True)

    sources = [
        {
            "chunk_index": i + 1,
            "doc_id": meta.get("doc_id", "unknown"),
            "trust_score": meta.get("trust", 100.0),
            "relevance_score": round(score * 100, 1),
            "excerpt": chunk[:200] + "..."
        }
        for i, (chunk, meta, score) in enumerate(zip(
            retrieval_result["chunks"],
            retrieval_result["metadatas"],
            retrieval_result["scores"]
        ))
    ]

    return {"answer": answer, "answerable": True, "sources": sources}

@app.get("/documents")
def get_documents(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    docs = get_user_documents(str(user["id"]))
    return {"documents": docs}

@app.get("/history")
def get_history(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    history = get_user_chat_history(str(user["id"]))
    return {"history": history}

@app.delete("/history")
def clear_history(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return {"message": "History cleared."}