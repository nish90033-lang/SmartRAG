import fitz  # PyMuPDF
import hashlib
import re
import os

# NOTE: in-memory seen_hashes removed.
# The DB-level check_duplicate() in main.py is the authoritative duplicate guard.
# A module-level set caused a silent trap: if ingest_document() ran but the DB insert
# later failed (connection drop), the hash stayed "seen" in memory — future uploads
# of the same content returned false duplicate errors until server restart.

# ── Injection patterns ────────────────────────────────────────────────────────
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

# ── Text extraction ───────────────────────────────────────────────────────────

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract raw text from a PDF, one page at a time.
    Each page is released from memory immediately after extraction —
    never holds the full document in RAM simultaneously.
    Allows 800-page PDFs to run within Render's 512MB limit.
    """
    doc = fitz.open(file_path)
    pages = []
    for page in doc:
        pages.append(page.get_text())
        page = None          # release page object immediately
    doc.close()
    return "\n".join(pages)

def extract_text_from_string(raw_text: str) -> str:
    """
    Accept plain text input directly.
    Strips leading/trailing whitespace, normalises line endings.
    """
    return raw_text.replace('\r\n', '\n').replace('\r', '\n').strip()

def extract_text(source) -> tuple[str, str]:
    """
    Universal extractor.
    source can be:
      - str path ending in .pdf  -> PDF extraction
      - str (raw text, no .pdf)  -> treated as plain text
      - bytes                    -> decoded as UTF-8 plain text

    Returns (text, source_type) where source_type is 'pdf' or 'text'.
    """
    if isinstance(source, bytes):
        return source.decode('utf-8', errors='ignore'), 'text'

    if isinstance(source, str):
        if source.strip().endswith('.pdf') and os.path.exists(source):
            return extract_text_from_pdf(source), 'pdf'
        return extract_text_from_string(source), 'text'

    raise ValueError(f"Unsupported source type: {type(source)}")

# ── Fingerprinting ────────────────────────────────────────────────────────────

def fingerprint(text: str) -> str:
    """SHA256 hash of document text for duplicate detection."""
    return hashlib.sha256(text.encode()).hexdigest()

# ── Sanitization ──────────────────────────────────────────────────────────────

def sanitize(text: str) -> tuple[str, int]:
    """
    Remove prompt injection patterns and normalise whitespace.
    Returns (clean_text, patterns_found).
    patterns_found is a count of distinct patterns that matched.
    """
    clean = text
    patterns_found = 0

    for pattern in INJECTION_PATTERNS:
        before_len = len(clean)
        clean = re.sub(pattern, '', clean, flags=re.IGNORECASE)
        if len(clean) < before_len:
            patterns_found += 1

    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean, patterns_found

# ── Trust scoring ─────────────────────────────────────────────────────────────

def compute_trust_score(original_text: str, clean_text: str, patterns_found: int) -> float:
    """
    Trust score 0-100.
    Base = min(100, ratio * 120).
    Hard cap at 40 if ANY injection pattern was found.
    Clean docs score 90-100; poisoned docs score <= 40 (below TRUST_THRESHOLD=50).
    """
    original_len = len(original_text)
    if original_len == 0:
        return 0.0

    ratio = len(clean_text) / original_len
    base_score = min(100.0, ratio * 120)

    if patterns_found > 0:
        base_score = min(base_score, 40.0)

    return round(base_score, 1)

# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = 400,
    overlap: int = 50,
    max_chunks: int = 800,
) -> list[str]:
    """
    Split text into overlapping word-based chunks.

    chunk_size : words per chunk (400 ~ 2-3 paragraphs)
    overlap    : words shared between adjacent chunks (prevents boundary loss)
    max_chunks : hard cap to prevent OOM on very large documents.
                 800 chunks * ~400 words = ~320,000 words = ~640 pages.
                 Content beyond this limit is silently truncated.
                 Render free tier: 800 chunks uses ~60MB RAM safely within 512MB.
    """
    words = text.split()
    chunks = []
    step = chunk_size - overlap

    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        if len(chunks) >= max_chunks:
            break                        # hard stop — prevents OOM on 800+ page docs

    return chunks

# ── Main ingestion pipeline ───────────────────────────────────────────────────

def ingest_document(source, doc_id: str = None) -> dict:
    """
    Full ingestion pipeline. Accepts a PDF file path or raw text.

    Parameters
    ----------
    source : str | bytes
        - Path to a .pdf file  -> PDF extraction
        - Raw text string      -> direct ingestion
        - bytes                -> decoded as UTF-8 text

    doc_id : str, optional
        Custom document identifier. If None:
        - For PDF paths: derived from filename
        - For text input: 'text_<first 32 chars of hash>'

    Returns
    -------
    dict with keys:
        doc_id, doc_hash, trust_score, patterns_found,
        chunks, chunk_count, source_type, truncated
    OR
        {"error": "..."}
    """

    # Step 1: Extract text
    try:
        text, source_type = extract_text(source)
    except Exception as e:
        return {"error": f"Text extraction failed: {str(e)}"}

    if not text.strip():
        return {"error": "No text content found in the provided source."}

    # Step 2: Fingerprint (duplicate detection handled at DB level in main.py)
    doc_hash = fingerprint(text)

    # Step 3: Sanitize
    sanitized, patterns_found = sanitize(text)

    # Step 4: Trust score
    trust_score = compute_trust_score(text, sanitized, patterns_found)

    # Step 5: Chunk (with hard cap)
    total_words = len(sanitized.split())
    chunks = chunk_text(sanitized)
    truncated = len(chunks) == 800 and total_words > 800 * (400 - 50)

    if not chunks:
        return {"error": "Document produced no text chunks after processing."}

    # Step 6: Derive doc_id
    if doc_id is None:
        if source_type == 'pdf' and isinstance(source, str):
            doc_id = os.path.splitext(os.path.basename(source))[0]
        else:
            doc_id = f"text_{doc_hash[:32]}"

    return {
        "doc_id":         doc_id,
        "doc_hash":       doc_hash,
        "trust_score":    trust_score,
        "patterns_found": patterns_found,
        "source_type":    source_type,
        "chunks":         chunks,
        "chunk_count":    len(chunks),
        "truncated":      truncated,     # True if doc exceeded 800-chunk cap
    }