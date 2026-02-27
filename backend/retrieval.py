from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi
import numpy as np

# In-memory stores
all_chunks = []
all_metadatas = []
vectorizer = TfidfVectorizer(max_features=5000)
tfidf_matrix = None

def store_chunks(chunks: list, doc_id: str, trust_score: float):
    global all_chunks, all_metadatas, tfidf_matrix, vectorizer

    print(f"Storing {len(chunks)} chunks...")
    ids_start = len(all_chunks)
    metadatas = [{"doc_id": doc_id, "trust": trust_score, "chunk_index": i} for i in range(len(chunks))]

    all_chunks.extend(chunks)
    all_metadatas.extend(metadatas)

    # Refit TF-IDF on all chunks
    tfidf_matrix = vectorizer.fit_transform(all_chunks)
    print(f"Stored {len(chunks)} chunks for doc '{doc_id}'")

def vector_search(query: str, top_k: int = 10) -> list:
    global tfidf_matrix
    if tfidf_matrix is None or len(all_chunks) == 0:
        return []
    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, tfidf_matrix)[0]
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [(all_chunks[i], all_metadatas[i], float(scores[i])) for i in top_indices]

def bm25_search(query: str, top_k: int = 10) -> list:
    if not all_chunks:
        return []
    tokenized_corpus = [c.split() for c in all_chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(query.split())
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [(all_chunks[i], all_metadatas[i], float(scores[i])) for i in top_indices]

def hybrid_search(query: str, top_k: int = 10) -> list:
    vec_results = vector_search(query, top_k)
    bm25_results = bm25_search(query, top_k)
    seen = {}
    for chunk, meta, score in vec_results + bm25_results:
        if chunk not in seen or score > seen[chunk][1]:
            seen[chunk] = (meta, score)
    merged = [(chunk, meta, score) for chunk, (meta, score) in seen.items()]
    merged.sort(key=lambda x: -x[2])
    return merged[:top_k]

def rerank(query: str, candidates: list) -> list:
    reranked = []
    doc_chunk_count = {}
    for chunk, meta, base_score in candidates:
        doc_id = meta.get("doc_id", "unknown")
        trust = meta.get("trust", 1.0)
        if doc_chunk_count.get(doc_id, 0) >= 3:
            continue
        final_score = base_score * trust
        reranked.append((chunk, meta, final_score))
        doc_chunk_count[doc_id] = doc_chunk_count.get(doc_id, 0) + 1
    reranked.sort(key=lambda x: -x[2])
    return reranked[:5]

def is_answerable(candidates: list, threshold: float = 0.1) -> bool:
    if not candidates:
        return False
    return candidates[0][2] >= threshold

def retrieve(query: str) -> dict:
    candidates = hybrid_search(query)
    reranked = rerank(query, candidates)
    answerable = is_answerable(reranked)
    return {
        "answerable": answerable,
        "chunks": [c[0] for c in reranked],
        "metadatas": [c[1] for c in reranked],
        "scores": [c[2] for c in reranked]
    }