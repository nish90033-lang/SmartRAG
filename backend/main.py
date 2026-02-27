from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os

from ingest import ingest_document
from retrieval import store_chunks
from llm import answer

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

chat_history = []

class QueryRequest(BaseModel):
    question: str
    use_llm: bool = True

@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"status": "SmartRAG is running"}

@app.options("/{full_path:path}")
async def preflight_handler():
    return {"message": "Preflight OK"}

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    result = ingest_document(file_path)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    store_chunks(result["chunks"], result["doc_id"], result["trust_score"])
    return {
        "message": "Document uploaded and indexed successfully.",
        "doc_id": result["doc_id"],
        "trust_score": result["trust_score"],
        "chunk_count": result["chunk_count"]
    }

@app.post("/query")
def query_document(request: QueryRequest):
    result = answer(request.question, use_llm=request.use_llm)
    chat_history.append({
        "question": request.question,
        "answer": result["answer"],
        "answerable": result["answerable"]
    })
    return result

@app.get("/history")
def get_history():
    return {"history": chat_history}

@app.delete("/history")
def clear_history():
    chat_history.clear()
    return {"message": "History cleared."}