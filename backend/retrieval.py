import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi
from typing import Optional


TRUST_THRESHOLD = 50    
TOP_K           = 20    
FINAL_K         = 9     
MAX_PER_DOC     = 3     









vectorizer = HashingVectorizer(
    n_features=2**18,       
    alternate_sign=False,   
    norm='l2',              
    analyzer='word',
    ngram_range=(1, 2),     
    stop_words='english',
)



def hybrid_search(query: str, chunks: list[str], weights: tuple = (0.7, 0.3)) -> list[float]:
    """
    Run TF-IDF (HashingVectorizer) and BM25 in parallel.
    Merge scores: final = tfidf_weight * tfidf_score + bm25_weight * bm25_score.
    Returns a list of combined scores, one per chunk.
    """
    if not chunks:
        return []

    tfidf_w, bm25_w = weights

    
    all_texts = chunks + [query]
    matrix        = vectorizer.transform(all_texts)   
    chunk_vectors = matrix[:-1]
    query_vector  = matrix[-1]

    tfidf_scores = cosine_similarity(query_vector, chunk_vectors).flatten()

    
    tokenized_chunks = [c.lower().split() for c in chunks]
    tokenized_query  = query.lower().split()
    bm25 = BM25Okapi(tokenized_chunks)
    bm25_raw = np.array(bm25.get_scores(tokenized_query))

    
    
    
    
    bm25_raw = np.maximum(bm25_raw, 0)

    
    bm25_max = bm25_raw.max()
    bm25_scores = bm25_raw / bm25_max if bm25_max > 0 else bm25_raw

    combined = tfidf_w * tfidf_scores + bm25_w * bm25_scores
    return combined.tolist()



def rerank(
    chunks: list[dict],
    scores: list[float],
    max_per_doc: int = MAX_PER_DOC,
    final_k: int = FINAL_K,
) -> list[dict]:
    """
    Rerank by relevance * (trust / 100).
    Applies MAX_PER_DOC diversity cap across documents.
    Returns top final_k chunks sorted by final_score descending.
    """
    ranked = []
    for chunk, score in zip(chunks, scores):
        trust = chunk.get('trust_score', 100)
        final_score = score * (trust / 100)
        ranked.append({
            **chunk,
            'relevance_score': round(score * 100, 1),
            'final_score': final_score,
        })

    ranked.sort(key=lambda x: x['final_score'], reverse=True)

    doc_counts: dict[str, int] = {}
    selected = []
    for item in ranked:
        doc_id = item.get('doc_id', 'unknown')
        if doc_counts.get(doc_id, 0) < max_per_doc:
            selected.append(item)
            doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1
        if len(selected) >= final_k:
            break

    return selected



def retrieve(
    query: str,
    all_chunks: list[dict],
    doc_ids: Optional[list[str]] = None,
) -> dict:
    """
    Full retrieval pipeline.

    Parameters
    ----------
    query      : User question string
    all_chunks : List of chunk dicts from PostgreSQL.
                 Each must have: content, doc_id, trust_score, chunk_index
    doc_ids    : Optional list of doc_ids to restrict search to.
                 None = search across all user's documents.

    Returns
    -------
    dict:
        answerable    : bool
        chunks        : list of reranked chunk dicts  (if answerable)
        blocked_reason: str | None
    """

    
    pool = [c for c in all_chunks if c.get('doc_id') in doc_ids] if doc_ids else all_chunks

    if not pool:
        return {
            "answerable": False,
            "chunks": [],
            "blocked_reason": "No documents found for the given selection.",
        }

    
    trusted_pool = [c for c in pool if c.get('trust_score', 100) >= TRUST_THRESHOLD]

    if not trusted_pool:
        return {
            "answerable": False,
            "chunks": [],
            "blocked_reason": (
                "All selected documents were blocked due to low trust scores "
                "(prompt injection content detected at ingestion). "
                "Please upload clean documents."
            ),
        }

    
    texts  = [c['content'] for c in trusted_pool]
    scores = hybrid_search(query, texts)

    
    scored = sorted(zip(trusted_pool, scores), key=lambda x: x[1], reverse=True)[:TOP_K]
    top_chunks = [x[0] for x in scored]
    top_scores = [x[1] for x in scored]

    
    
    
    
    if not top_scores or top_scores[0] < 0.02:
        return {
            "answerable": False,
            "chunks": [],
            "blocked_reason": "No sufficiently relevant content found for this query.",
        }

    
    final_chunks = rerank(top_chunks, top_scores)

    return {
        "answerable": True,
        "chunks": final_chunks,
        "blocked_reason": None,
    }