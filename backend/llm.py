import os
from groq import Groq

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
                    "Answer using ONLY the information provided in the context. "
                    "Do not use any external knowledge. "
                    "If the answer is not in the context, say exactly: "
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