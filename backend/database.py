import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://nnlbggpbudktmzagigcj.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_user_from_token(token: str):
    """Verify JWT token and return user."""
    try:
        user = supabase.auth.get_user(token)
        return user.user
    except Exception:
        return None

def save_document(user_id: str, doc_id: str, doc_hash: str, trust_score: float, chunk_count: int, filename: str):
    """Save document metadata to Supabase."""
    try:
        supabase.table("documents").insert({
            "user_id": user_id,
            "doc_id": doc_id,
            "doc_hash": doc_hash,
            "trust_score": trust_score,
            "chunk_count": chunk_count,
            "filename": filename
        }).execute()
    except Exception as e:
        print(f"Error saving document: {e}")

def get_user_documents(user_id: str):
    """Get all documents for a user."""
    try:
        res = supabase.table("documents").select("*").eq("user_id", user_id).execute()
        return res.data
    except Exception as e:
        print(f"Error fetching documents: {e}")
        return []

def save_chunks(user_id: str, doc_id: str, chunks: list, trust_score: float):
    """Save all chunks for a document."""
    try:
        rows = [
            {
                "user_id": user_id,
                "doc_id": doc_id,
                "chunk_index": i,
                "content": chunk,
                "trust_score": trust_score
            }
            for i, chunk in enumerate(chunks)
        ]
        # Insert in batches of 100
        for i in range(0, len(rows), 100):
            supabase.table("chunks").insert(rows[i:i+100]).execute()
    except Exception as e:
        print(f"Error saving chunks: {e}")

def get_user_chunks(user_id: str):
    """Get all chunks for a user across all their documents."""
    try:
        res = supabase.table("chunks").select("*").eq("user_id", user_id).execute()
        return res.data
    except Exception as e:
        print(f"Error fetching chunks: {e}")
        return []

def save_chat(user_id: str, question: str, answer: str, answerable: bool):
    """Save a chat message to history."""
    try:
        supabase.table("chat_history").insert({
            "user_id": user_id,
            "question": question,
            "answer": answer,
            "answerable": answerable
        }).execute()
    except Exception as e:
        print(f"Error saving chat: {e}")

def get_user_chat_history(user_id: str):
    """Get chat history for a user."""
    try:
        res = supabase.table("chat_history").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        return []

def check_duplicate(user_id: str, doc_hash: str) -> bool:
    """Check if user already uploaded this document."""
    try:
        res = supabase.table("documents").select("id").eq("user_id", user_id).eq("doc_hash", doc_hash).execute()
        return len(res.data) > 0
    except Exception:
        return False