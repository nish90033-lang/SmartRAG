from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi
import numpy as np

def build_user_index(chunks: list):
    """Build a TF-IDF index for a user's chunks."""
    vectorizer = TfidfVectorizer(max_features=5000)
    matrix = vectorizer.fit_transform(chunks)
    return vectorizer, matrix

def vector_search(query: str, chunks: list, vectorizer, matrix, top_k: int = 10) -> list:
    if not chunks:
        return []
    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, matrix)[0]
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [(chunks[i], float(scores[i])) for i in top_indices]

def bm25_search(query: str, chunks: list, top_k: int = 10) -> list:
    if not chunks:
        return []
    tokenized = [c.split() for c in chunks]
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(query.split())
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [(chunks[i], float(scores[i])) for i in top_indices]

def hybrid_search(query: str, chunks: list, metadatas: list, top_k: int = 10) -> list:
    vectorizer, matrix = build_user_index(chunks)
    vec_results = vector_search(query, chunks, vectorizer, matrix, top_k)
    bm25_results = bm25_search(query, chunks, top_k)

    seen = {}
    for chunk, score in vec_results + bm25_results:
        if chunk not in seen or score > seen[chunk]:
            seen[chunk] = score

    # Match back to metadatas
    chunk_to_meta = {c: m for c, m in zip(chunks, metadatas)}
    merged = [(chunk, chunk_to_meta.get(chunk, {}), score) for chunk, score in seen.items()]
    merged.sort(key=lambda x: -x[2])
    return merged[:top_k]

def rerank(candidates: list) -> list:
    reranked = []
    doc_chunk_count = {}
    for chunk, meta, base_score in candidates:
        doc_id = meta.get("doc_id", "unknown")
        trust = meta.get("trust", 100.0) / 100.0
        if doc_chunk_count.get(doc_id, 0) >= 3:
            continue
        final_score = base_score * trust
        reranked.append((chunk, meta, final_score))
        doc_chunk_count[doc_id] = doc_chunk_count.get(doc_id, 0) + 1
    reranked.sort(key=lambda x: -x[2])
    return reranked[:5]

def is_answerable(candidates: list, threshold: float = 0.05) -> bool:
    if not candidates:
        return False
    return candidates[0][2] >= threshold

def retrieve(query: str, chunks: list, metadatas: list) -> dict:
    candidates = hybrid_search(query, chunks, metadatas)
    reranked = rerank(candidates)
    answerable = is_answerable(reranked)
    return {
        "answerable": answerable,
        "chunks": [c[0] for c in reranked],
        "metadatas": [c[1] for c in reranked],
        "scores": [c[2] for c in reranked]
    }