from retrieval import retrieve
from groq import Groq
import os

# Paste your Groq API key here
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY)

def generate_answer(query: str, chunks: list) -> str:
    """Call Groq LLM with only the retrieved chunks as context."""
    if not chunks:
        return "I don't have enough information to answer that question."

    context = "\n\n---\n\n".join(chunks)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise question-answering assistant. "
                    "Answer using ONLY the provided context. "
                    "Do not use any external knowledge. "
                    "If the answer is not in the context, say: "
                    "'I don't have enough information to answer that.'"
                )
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}"
            }
        ],
        temperature=0.2,
        max_tokens=512
    )

    return response.choices[0].message.content


def fallback_answer(chunks: list) -> str:
    """Non-LLM fallback — returns raw excerpt directly."""
    if not chunks:
        return "No relevant information found."
    return f"Most relevant excerpt:\n\n{chunks[0][:500]}..."


def answer(query: str, use_llm: bool = True) -> dict:
    """Full answer pipeline with retrieval + LLM + explainability."""
    retrieval_result = retrieve(query)

    if not retrieval_result["answerable"]:
        return {
            "answer": "I don't have enough information in the uploaded documents to answer that.",
            "answerable": False,
            "sources": []
        }

    chunks = retrieval_result["chunks"]
    metadatas = retrieval_result["metadatas"]
    scores = retrieval_result["scores"]

    if use_llm:
        raw_answer = generate_answer(query, chunks)
    else:
        raw_answer = fallback_answer(chunks)

    sources = []
    for i, (chunk, meta, score) in enumerate(zip(chunks, metadatas, scores)):
        sources.append({
            "chunk_index": i + 1,
            "doc_id": meta.get("doc_id", "unknown"),
            "trust_score": meta.get("trust", 1.0),
            "relevance_score": round(score, 4),
            "excerpt": chunk[:200] + "..."
        })

    return {
        "answer": raw_answer,
        "answerable": True,
        "sources": sources
    }