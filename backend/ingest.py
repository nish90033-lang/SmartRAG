import fitz  # PyMuPDF
import hashlib
import re
import os

# Store seen hashes to detect duplicates
seen_hashes = set()

def extract_text(file_path: str) -> str:
    """Extract raw text from a PDF file."""
    doc = fitz.open(file_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text

def fingerprint(text: str) -> str:
    """Generate a SHA256 hash of the document text."""
    return hashlib.sha256(text.encode()).hexdigest()

def is_duplicate(hash_val: str) -> bool:
    """Check if this document has been uploaded before."""
    if hash_val in seen_hashes:
        return True
    seen_hashes.add(hash_val)
    return False

def sanitize(text: str) -> str:
    """Remove prompt injection patterns and normalize whitespace."""
    # Remove common injection phrases
    injection_patterns = [
        r'(?i)ignore previous instructions',
        r'(?i)you are now',
        r'(?i)system:',
        r'(?i)disregard all',
        r'(?i)forget everything',
    ]
    for pattern in injection_patterns:
        text = re.sub(pattern, '', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def compute_trust_score(text: str, sanitized_text: str) -> float:
    """
    Assign a trust score between 0 and 1.
    Penalize docs where a lot of content was removed during sanitization.
    """
    original_len = len(text)
    sanitized_len = len(sanitized_text)
    if original_len == 0:
        return 0.0
    ratio = sanitized_len / original_len
    # If more than 20% was stripped, lower the trust score
    trust = min(100.0, ratio * 120)
    return round(trust, 1)

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list:
    """Split text into overlapping word-based chunks."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks

def ingest_document(file_path: str) -> dict:
    """
    Full ingestion pipeline for a single document.
    Returns a dict with chunks, trust score, doc_id, or an error.
    """
    # Step 1: Extract text
    text = extract_text(file_path)
    if not text.strip():
        return {"error": "Could not extract text from document."}

    # Step 2: Fingerprint & duplicate check
    doc_hash = fingerprint(text)
    if is_duplicate(doc_hash):
        return {"error": "Duplicate document detected. Skipping."}

    # Step 3: Sanitize
    sanitized = sanitize(text)

    # Step 4: Trust score
    trust_score = compute_trust_score(text, sanitized)

    # Step 5: Chunk
    chunks = chunk_text(sanitized)

    # Use filename as doc_id
    doc_id = os.path.splitext(os.path.basename(file_path))[0]

    return {
        "doc_id": doc_id,
        "doc_hash": doc_hash,
        "trust_score": trust_score,
        "chunks": chunks,
        "chunk_count": len(chunks)
    }
