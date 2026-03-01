import psycopg2
import psycopg2.extras
import bcrypt
import jwt
import os
import uuid
from datetime import datetime, timedelta

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://smartrag_db_user:MpPdvqETkwVGQejpQuF3TX4ei3lItebm@dpg-d6ho9gpdrdic73cp4eng-a/smartrag_db")
JWT_SECRET = os.environ.get("JWT_SECRET", "smartrag-super-secret-key-2024")

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            doc_hash TEXT NOT NULL,
            trust_score REAL DEFAULT 100.0,
            chunk_count INTEGER DEFAULT 0,
            filename TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            trust_score REAL DEFAULT 100.0,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            answerable BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cursor.close()
    conn.close()

init_db()

# ─── AUTH ───────────────────────────────────────────

def create_user(email: str, password: str) -> dict:
    conn = get_db()
    try:
        cursor = conn.cursor()
        user_id = str(uuid.uuid4())
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cursor.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s)",
            (user_id, email, password_hash)
        )
        conn.commit()
        return {"id": user_id, "email": email}
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()

def login_user(email: str, password: str) -> dict:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user:
            return None
        if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            return None
        return {"id": user["id"], "email": user["email"]}
    finally:
        cursor.close()
        conn.close()

def create_token(user_id: str, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def get_user_from_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return {"id": payload["user_id"], "email": payload["email"]}
    except Exception:
        return None

# ─── DOCUMENTS ──────────────────────────────────────

def save_document(user_id: str, doc_id: str, doc_hash: str, trust_score: float, chunk_count: int, filename: str):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO documents (id, user_id, doc_id, doc_hash, trust_score, chunk_count, filename) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (str(uuid.uuid4()), user_id, doc_id, doc_hash, trust_score, chunk_count, filename)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def get_user_documents(user_id: str) -> list:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM documents WHERE user_id = %s ORDER BY created_at DESC", (user_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

def check_duplicate(user_id: str, doc_hash: str) -> bool:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM documents WHERE user_id = %s AND doc_hash = %s", (user_id, doc_hash)
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()
        conn.close()

# ─── CHUNKS ─────────────────────────────────────────

def save_chunks(user_id: str, doc_id: str, chunks: list, trust_score: float):
    conn = get_db()
    try:
        cursor = conn.cursor()
        for i, chunk in enumerate(chunks):
            cursor.execute(
                "INSERT INTO chunks (id, user_id, doc_id, chunk_index, content, trust_score) VALUES (%s, %s, %s, %s, %s, %s)",
                (str(uuid.uuid4()), user_id, doc_id, i, chunk, trust_score)
            )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def get_user_chunks(user_id: str) -> list:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chunks WHERE user_id = %s", (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

# ─── CHAT HISTORY ───────────────────────────────────

def save_chat(user_id: str, question: str, answer: str, answerable: bool):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_history (id, user_id, question, answer, answerable) VALUES (%s, %s, %s, %s, %s)",
            (str(uuid.uuid4()), user_id, question, answer, answerable)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def get_user_chat_history(user_id: str) -> list:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM chat_history WHERE user_id = %s ORDER BY created_at DESC", (user_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

