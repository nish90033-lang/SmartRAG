from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
import shutil
import os

from ingest import ingest_document
from retrieval import store_chunks
from llm import answer

app = FastAPI(title="SmartRAG API")

# ---------------------------
# CORS CONFIGURATION
# ---------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://smart-rag.vercel.app",  # your production domain
        "https://smart-rag-git-main-nish90033-langs-projects.vercel.app",  # preview
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional but useful behind proxies like Render
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

# ---------------------------
# FILE STORAGE SETUP
# ---------------------------
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------------------
# IN-MEMORY CHAT HISTORY
# ---------------------------
chat_history = []

# ---------------------------
# REQUEST MODEL
# ---------------------------
class QueryRequest(BaseModel):
    question: str
    use_llm: bool = False


# ---------------------------
# ROOT ROUTE
# ---------------------------
@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"status": "SmartRAG is running"}


# ---------------------------
# PRE-FLIGHT HANDLER (Safety)
# ---------------------------
@app.options("/{full_path:path}")
async def preflight_handler():
    return {"message": "Preflight OK"}


# ---------------------------
# UPLOAD ENDPOINT
# ---------------------------
@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a PDF, ingest it, and store its chunks."""

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    result = ingest_document(file_path)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    store_chunks(
        result["chunks"],
        result["doc_id"],
        result["trust_score"]
    )

    return {
        "message": "Document uploaded and indexed successfully.",
        "doc_id": result["doc_id"],
        "trust_score": result["trust_score"],
        "chunk_count": result["chunk_count"]
    }


# ---------------------------
# QUERY ENDPOINT
# ---------------------------
@app.post("/query")
def query_document(request: QueryRequest):
    """Ask a question and get an answer."""

    result = answer(request.question, use_llm=request.use_llm)

    chat_history.append({
        "question": request.question,
        "answer": result["answer"],
        "answerable": result["answerable"]
    })

    return result


# ---------------------------
# HISTORY ENDPOINTS
# ---------------------------
@app.get("/history")
def get_history():
    return {"history": chat_history}


@app.delete("/history")
def clear_history():
    chat_history.clear()
    return {"message": "History cleared."}