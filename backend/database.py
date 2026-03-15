# database.py — SmartRAG database layer with ECC (ES256) JWT authentication
#
# CHANGES FROM OLD VERSION
# ─────────────────────────────────────────────────────────────────────────────
# OLD: create_token()        used PyJWT HS256 with JWT_SECRET (symmetric)
# NEW: create_token()        uses ecc_auth.create_ecc_token() (ES256, asymmetric)
#
# OLD: get_user_from_token() used jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
# NEW: get_user_from_token() uses ecc_auth.verify_ecc_token() (P-256 public key)
#
# Everything else (DB queries, bcrypt, user model) is UNCHANGED.
# ─────────────────────────────────────────────────────────────────────────────

import os
import uuid
import datetime
import psycopg2
import psycopg2.extras
import bcrypt
from dotenv import load_dotenv

from ecc_auth import create_ecc_token, verify_ecc_token

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")


# ── DB connection ─────────────────────────────────────────────────────────────

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn


# ── Schema initialisation (run on startup) ────────────────────────────────────

def init_db():
    """Create all tables if they do not exist."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
                doc_id      TEXT NOT NULL,
                filename    TEXT,
                doc_hash    TEXT,
                trust_score REAL,
                chunk_count INT,
                created_at  TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
                doc_id      TEXT NOT NULL,
                chunk_index INT,
                content     TEXT,
                trust_score REAL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
                question    TEXT,
                answer      TEXT,
                answerable  BOOLEAN,
                created_at  TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
    finally:
        cur.close()
        conn.close()


# ── Auth ──────────────────────────────────────────────────────────────────────

def create_user(email: str, password: str) -> dict | None:
    """
    Register a new user. Returns user dict or None if email already exists.
    Password is hashed with bcrypt before storage.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        # Check duplicate
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            return None

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user_id = str(uuid.uuid4())

        cur.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s) RETURNING id, email",
            (user_id, email, pw_hash)
        )
        row = cur.fetchone()
        conn.commit()
        return {"id": str(row["id"]), "email": row["email"]}
    except Exception:
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()


def login_user(email: str, password: str) -> dict | None:
    """
    Authenticate a user. Returns user dict or None if credentials are wrong.
    Uses bcrypt.checkpw for constant-time comparison.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            "SELECT id, email, password_hash FROM users WHERE email = %s",
            (email,)
        )
        row = cur.fetchone()
        if not row:
            return None
        if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
            return None
        return {"id": str(row["id"]), "email": row["email"]}
    finally:
        cur.close()
        conn.close()


def create_token(user_id: str, email: str) -> str:
    """
    Issue an ES256 JWT signed with the P-256 private key.

    ── SECURITY UPGRADE ──────────────────────────────────────────────────────
    OLD: jwt.encode(payload, JWT_SECRET, algorithm="HS256")
         — symmetric: same secret signs AND verifies.
         — if JWT_SECRET leaks, anyone can forge tokens forever.

    NEW: ecc_auth.create_ecc_token(user_id, email)
         — asymmetric: private key signs, public key verifies.
         — public key can be shared freely at GET /auth/public-key.
         — a leaked public key cannot forge new tokens.
         — a DB breach cannot produce valid signatures without the private key.
    ──────────────────────────────────────────────────────────────────────────
    """
    return create_ecc_token(user_id, email)


def get_user_from_token(token: str) -> dict | None:
    """
    Verify an ES256 JWT and return the user dict from the DB.

    Verification uses the P-256 public key via ecc_auth.verify_ecc_token().
    Returns None if the token is invalid, expired, or the user no longer exists.
    """
    payload = verify_ecc_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT id, email FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": str(row["id"]), "email": row["email"]}
    finally:
        cur.close()
        conn.close()


# ── Documents ─────────────────────────────────────────────────────────────────

def save_document(user_id, doc_id, doc_hash, trust_score, chunk_count, filename):
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO documents (id, user_id, doc_id, filename, doc_hash, trust_score, chunk_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (str(uuid.uuid4()), user_id, doc_id, filename, doc_hash, trust_score, chunk_count))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_user_documents(user_id: str) -> list:
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT doc_id, filename, trust_score, chunk_count, created_at
            FROM documents
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        cur.close()
        conn.close()


def check_duplicate(user_id: str, doc_hash: str) -> bool:
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            "SELECT id FROM documents WHERE user_id = %s AND doc_hash = %s",
            (user_id, doc_hash)
        )
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


# ── Chunks ────────────────────────────────────────────────────────────────────

def save_chunks(user_id: str, doc_id: str, chunks: list, trust_score: float):
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.executemany("""
            INSERT INTO chunks (id, user_id, doc_id, chunk_index, content, trust_score)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, [(str(uuid.uuid4()), user_id, doc_id, i, chunk, trust_score)
              for i, chunk in enumerate(chunks)])
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_user_chunks(user_id: str) -> list:
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT doc_id, chunk_index, content, trust_score
            FROM chunks
            WHERE user_id = %s
        """, (user_id,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        cur.close()
        conn.close()


# ── Chat history ──────────────────────────────────────────────────────────────

def save_chat(user_id: str, question: str, answer: str, answerable: bool):
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO chat_history (id, user_id, question, answer, answerable)
            VALUES (%s, %s, %s, %s, %s)
        """, (str(uuid.uuid4()), user_id, question, answer, answerable))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_user_chat_history(user_id: str) -> list:
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT question, answer, answerable, created_at
            FROM chat_history
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 50
        """, (user_id,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        cur.close()
        conn.close()