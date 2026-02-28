import sqlite3
import bcrypt
import jwt
import os
import uuid
from datetime import datetime, timedelta

DB_PATH = "smartrag.db"
JWT_SECRET = os.environ.get("JWT_SECRET", "smartrag-secret-key-change-in-production")


# ─────────────────────────────────────────────
# DB CONNECTION
# ─────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            doc_hash TEXT NOT NULL,
            trust_score REAL DEFAULT 100.0,
            chunk_count INTEGER DEFAULT 0,
            filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            trust_score REAL DEFAULT 100.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            answerable INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    conn.commit()
    conn.close()


# Initialize DB on import
init_db()


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def create_user(email: str, password: str) -> dict:
    conn = get_db()
    try:
        user_id = str(uuid.uuid4())
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        conn.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
            (user_id, email, password_hash)
        )
        conn.commit()

        return {"id": user_id, "email": email}

    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def login_user(email: str, password: str) -> dict:
    conn = get_db()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if not user:
            return None

        if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            return None

        return {"id": user["id"], "email": user["email"]}

    finally:
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
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ─────────────────────────────────────────────
# USERS (FOR INDEX REBUILD)
# ─────────────────────────────────────────────

def get_all_users() -> list:
    conn = get_db()
    try:
        rows = conn.execute("SELECT id, email FROM users").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ─────────────────────────────────────────────
# DOCUMENTS
# ─────────────────────────────────────────────

def save_document(user_id: str, doc_id: str, doc_hash: str,
                  trust_score: float, chunk_count: int, filename: str):
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO documents 
               (id, user_id, doc_id, doc_hash, trust_score, chunk_count, filename) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), user_id, doc_id, doc_hash,
             trust_score, chunk_count, filename)
        )
        conn.commit()
    finally:
        conn.close()


def get_user_documents(user_id: str) -> list:
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT * FROM documents 
               WHERE user_id = ? 
               ORDER BY created_at DESC""",
            (user_id,)
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


def check_duplicate(user_id: str, doc_hash: str) -> bool:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM documents WHERE user_id = ? AND doc_hash = ?",
            (user_id, doc_hash)
        ).fetchone()

        return row is not None
    finally:
        conn.close()


# ─────────────────────────────────────────────
# CHUNKS
# ─────────────────────────────────────────────

def save_chunks(user_id: str, doc_id: str,
                chunks: list, trust_score: float):
    conn = get_db()
    try:
        for i, chunk in enumerate(chunks):
            conn.execute(
                """INSERT INTO chunks 
                   (id, user_id, doc_id, chunk_index, content, trust_score) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), user_id, doc_id,
                 i, chunk, trust_score)
            )
        conn.commit()
    finally:
        conn.close()


def get_user_chunks(user_id: str) -> list:
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT * FROM chunks 
               WHERE user_id = ? 
               ORDER BY doc_id, chunk_index""",
            (user_id,)
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


# ─────────────────────────────────────────────
# CHAT HISTORY
# ─────────────────────────────────────────────

def save_chat(user_id: str, question: str,
              answer: str, answerable: bool):
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO chat_history 
               (id, user_id, question, answer, answerable) 
               VALUES (?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), user_id,
             question, answer,
             1 if answerable else 0)
        )
        conn.commit()
    finally:
        conn.close()


def get_user_chat_history(user_id: str) -> list:
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT * FROM chat_history 
               WHERE user_id = ? 
               ORDER BY created_at DESC""",
            (user_id,)
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()