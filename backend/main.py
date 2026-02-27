from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os

from ingest import ingest_document
from retrieval import store_chunks
from llm import answer

app = FastAPI(title="SmartRAG API")

# Allow frontend to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temp folder to save uploaded files
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Chat history store (in-memory)
chat_history = []

# Request model for query endpoint
class QueryRequest(BaseModel):
    question: str
    use_llm: bool = False  # Default to fallback mode for now


@app.get("/")
def root():
    return {"status": "SmartRAG is running"}


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a PDF, ingest it, and store its chunks."""

    # Save file to disk temporarily
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Run ingestion pipeline
    result = ingest_document(file_path)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Store chunks in ChromaDB + BM25
    store_chunks(result["chunks"], result["doc_id"], result["trust_score"])

    return {
        "message": "Document uploaded and indexed successfully.",
        "doc_id": result["doc_id"],
        "trust_score": result["trust_score"],
        "chunk_count": result["chunk_count"]
    }


@app.post("/query")
def query_document(request: QueryRequest):
    """Ask a question and get an answer from uploaded documents."""

    result = answer(request.question, use_llm=request.use_llm)

    # Save to chat history
    chat_history.append({
        "question": request.question,
        "answer": result["answer"],
        "answerable": result["answerable"]
    })

    return result


@app.get("/history")
def get_history():
    """Return full chat history."""
    return {"history": chat_history}


@app.delete("/history")
def clear_history():
    """Clear chat history."""
    chat_history.clear()
    return {"message": "History cleared."}