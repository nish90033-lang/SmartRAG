import os
from groq import Groq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY)

STRICT_FALLBACK = "I don't have enough information to answer that."


def generate_answer(query: str, chunks: list) -> str:
    """
    Call Groq LLM using only retrieved chunks.
    Strict grounding enforced.
    """

    if not chunks:
        return STRICT_FALLBACK

    context = "\n\n---\n\n".join(chunks)

    system_prompt = (
        "You are a highly precise document question-answering assistant.\n\n"
        "RULES:\n"
        "1. Answer ONLY using the provided context.\n"
        "2. Do NOT use external knowledge.\n"
        "3. If the answer is not explicitly supported by the context, respond EXACTLY with:\n"
        f"   {STRICT_FALLBACK}\n"
        "4. Be concise but complete.\n"
        "5. If the question asks for a summary or overview, summarize the context clearly.\n"
    )

    user_prompt = f"""
Context:
{context}

Question:
{query}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,   # Lower = more deterministic
        max_tokens=512
    )

    answer = response.choices[0].message.content.strip()

    return answer


def fallback_answer(chunks: list) -> str:
    """
    Non-LLM fallback — returns top excerpt.
    Useful if you want zero hallucination mode.
    """
    if not chunks:
        return STRICT_FALLBACK

    return f"Most relevant excerpt:\n\n{chunks[0][:700]}..."