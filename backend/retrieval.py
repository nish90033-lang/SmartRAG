import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi

_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model

def build_index(chunks: list):
    if not chunks:
        return None, None
    embeddings = get_embedding_model().encode(chunks, show_progress_bar=False)
    tokenized = [c.lower().split() for c in chunks]
    bm25 = BM25Okapi(tokenized)
    return embeddings, bm25

def semantic_search(query: str, chunks: list, embeddings, top_k: int = 10):
    query_emb = get_embedding_model().encode([query])
    scores = cosine_similarity(query_emb, embeddings)[0]
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [(chunks[i], float(scores[i])) for i in top_indices]

def keyword_search(query: str, chunks: list, bm25, top_k: int = 10):
    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [(chunks[i], float(scores[i])) for i in top_indices]

def hybrid_search(query: str, chunks: list, metadatas: list,
                  embeddings, bm25, top_k: int = 10):
    semantic_results = semantic_search(query, chunks, embeddings, top_k)
    keyword_results = keyword_search(query, chunks, bm25, top_k)

    combined_scores = {}
    for chunk, score in semantic_results:
        combined_scores[chunk] = combined_scores.get(chunk, 0) + score * 0.7
    for chunk, score in keyword_results:
        combined_scores[chunk] = combined_scores.get(chunk, 0) + score * 0.3

    chunk_to_meta = {c: m for c, m in zip(chunks, metadatas)}
    merged = [
        (chunk, chunk_to_meta.get(chunk, {}), score)
        for chunk, score in combined_scores.items()
    ]
    merged.sort(key=lambda x: -x[2])
    return merged[:top_k]

def rerank(candidates: list, max_per_doc: int = 3, final_k: int = 6):
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
        return {
            "answerable": False,
            "chunks": [],
            "metadatas": [],
            "scores": []
        }

    embeddings, bm25 = build_index(chunks)

    candidates = hybrid_search(query, chunks, metadatas, embeddings, bm25)
    reranked = rerank(candidates)

    return {
        "answerable": len(reranked) > 0,
        "chunks": [c[0] for c in reranked],
        "metadatas": [c[1] for c in reranked],
        "scores": [c[2] for c in reranked]
    }