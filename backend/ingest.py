import fitz  # PyMuPDF
import hashlib
import re
import os

# Store seen hashes to detect duplicates
seen_hashes = set()

# ── Expanded injection patterns (was 5, now 12) ──────────────────────────────
INJECTION_PATTERNS = [
    r'ignore\s+(all\s+)?previous\s+instructions',
    r'disregard\s+(all\s+)?',
    r'you\s+are\s+now',
    r'system\s*:',
    r'forget\s+(all\s+)?rules',
    r'forget\s+everything',
    r'reveal\s+(the\s+)?system\s+prompt',
    r'provide\s+.{0,20}api\s+key',
    r'new\s+persona',
    r'note\s+for\s+(language\s+)?models',
    r'ignore\s+all',
    r'jailbreak',
]

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

def sanitize(text: str) -> tuple[str, int]:
    """
    Remove prompt injection patterns and normalize whitespace.
    Returns (clean_text, patterns_found).
    """
    clean = text
    patterns_found = 0

    for pattern in INJECTION_PATTERNS:
        before_len = len(clean)
        clean = re.sub(pattern, '', clean, flags=re.IGNORECASE)
        if len(clean) < before_len:
            patterns_found += 1

    # Normalize whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean, patterns_found

def compute_trust_score(original_text: str, clean_text: str, patterns_found: int) -> float:
    """
    Assign a trust score between 0 and 100.
    - Base score from sanitization ratio
    - Hard cap at 40 if ANY injection pattern was detected
    """
    original_len = len(original_text)
    if original_len == 0:
        return 0.0

    ratio = len(clean_text) / original_len
    base_score = min(100.0, ratio * 120)

    # ── Hard cap: any injection found → trust capped at 40 ───────────────────
    if patterns_found > 0:
        base_score = min(base_score, 40.0)

    return round(base_score, 1)

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

    # Step 3: Sanitize — now returns (clean_text, patterns_found)
    sanitized, patterns_found = sanitize(text)

    # Step 4: Trust score — now uses patterns_found for hard cap
    trust_score = compute_trust_score(text, sanitized, patterns_found)

    # Step 5: Chunk
    chunks = chunk_text(sanitized)

    doc_id = os.path.splitext(os.path.basename(file_path))[0]

    return {
        "doc_id": doc_id,
        "doc_hash": doc_hash,
        "trust_score": trust_score,
        "patterns_found": patterns_found,   # useful for debugging/logging
        "chunks": chunks,
        "chunk_count": len(chunks)
    }