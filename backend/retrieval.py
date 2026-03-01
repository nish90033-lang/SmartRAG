from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi
import numpy as np

def vector_search(query: str, chunks: list, top_k: int = 10) -> list:
    if not chunks:
        return []
    vectorizer = TfidfVectorizer(max_features=5000)
    matrix = vectorizer.fit_transform(chunks)
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
    vec_results = vector_search(query, chunks, top_k)
    bm25_results = bm25_search(query, chunks, top_k)

    combined_scores = {}
    for chunk, score in vec_results:
        combined_scores[chunk] = combined_scores.get(chunk, 0) + score * 0.7
    for chunk, score in bm25_results:
        combined_scores[chunk] = combined_scores.get(chunk, 0) + score * 0.3

    chunk_to_meta = {c: m for c, m in zip(chunks, metadatas)}
    merged = [
        (chunk, chunk_to_meta.get(chunk, {}), score)
        for chunk, score in combined_scores.items()
    ]
    merged.sort(key=lambda x: -x[2])
    return merged[:top_k]

def rerank(candidates: list, max_per_doc: int = 3, final_k: int = 6) -> list:
    reranked = []
    doc_chunk_count = {}
    for chunk, meta, base_score in candidates:
        doc_id = meta.get("doc_id", "unknown")
        trust = meta.get("trust", 100.0) / 100.0
        if doc_chunk_count.get(doc_id, 0) >= max_per_doc:
            continue
        final_score = base_score * trust
        reranked.append((chunk, meta, final_score))
        doc_chunk_count[doc_id] = doc_chunk_count.get(doc_id, 0) + 1
    reranked.sort(key=lambda x: -x[2])
    return reranked[:final_k]

def retrieve(query: str, chunks: list, metadatas: list) -> dict:
    if not chunks:
        return {"answerable": False, "chunks": [], "metadatas": [], "scores": []}
    candidates = hybrid_search(query, chunks, metadatas)
    reranked = rerank(candidates)
    return {
        "answerable": len(reranked) > 0,
        "chunks": [c[0] for c in reranked],
        "metadatas": [c[1] for c in reranked],
        "scores": [c[2] for c in reranked]
    }

