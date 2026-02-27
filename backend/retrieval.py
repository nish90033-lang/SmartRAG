import chromadb
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
import numpy as np

# Load the embedding model (downloads once, then cached locally)
model = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize ChromaDB
chroma = chromadb.Client()
collection = chroma.get_or_create_collection("smartrag")

# In-memory store for BM25
all_chunks = []
all_metadatas = []

def embed(text: str) -> list:
    """Convert text to a vector embedding."""
    return model.encode(text).tolist()

def store_chunks(chunks: list, doc_id: str, trust_score: float):
    """Embed and store chunks in ChromaDB and in-memory BM25 index."""
    global all_chunks, all_metadatas

    for i, chunk in enumerate(chunks):
        vec = embed(chunk)
        chunk_id = f"{doc_id}_{i}"
        metadata = {"doc_id": doc_id, "trust": trust_score, "chunk_index": i}

        collection.add(
            documents=[chunk],
            embeddings=[vec],
            ids=[chunk_id],
            metadatas=[metadata]
        )

        all_chunks.append(chunk)
        all_metadatas.append(metadata)

    print(f"Stored {len(chunks)} chunks for doc '{doc_id}'")

def bm25_search(query: str, top_k: int = 10) -> list:
    """Keyword-based BM25 search over all stored chunks."""
    if not all_chunks:
        return []

    tokenized_corpus = [c.split() for c in all_chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(query.split())
    top_indices = np.argsort(scores)[::-1][:top_k]

    return [(all_chunks[i], all_metadatas[i], float(scores[i])) for i in top_indices]

def vector_search(query: str, top_k: int = 10) -> list:
    """Semantic vector search using ChromaDB."""
    query_vec = embed(query)
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=min(top_k, collection.count())
    )

    chunks = results['documents'][0]
    metadatas = results['metadatas'][0]
    distances = results['distances'][0]

    # Convert distance to similarity score (ChromaDB returns L2 distance)
    similarities = [1 / (1 + d) for d in distances]

    return list(zip(chunks, metadatas, similarities))

def hybrid_search(query: str, top_k: int = 10) -> list:
    """Combine BM25 + vector search results into a single candidate pool."""
    vec_results = vector_search(query, top_k)
    bm25_results = bm25_search(query, top_k)

    # Merge by chunk text, keeping highest score per chunk
    seen = {}
    for chunk, meta, score in vec_results + bm25_results:
        if chunk not in seen or score > seen[chunk][1]:
            seen[chunk] = (meta, score)

    # Sort by score descending
    merged = [(chunk, meta, score) for chunk, (meta, score) in seen.items()]
    merged.sort(key=lambda x: -x[2])

    return merged[:top_k]

def rerank(query: str, candidates: list) -> list:
    """
    Rerank candidates by combining similarity score with trust score.
    Also limits chunks per document to ensure diversity.
    """
    query_vec = np.array(embed(query))
    reranked = []
    doc_chunk_count = {}

    for chunk, meta, base_score in candidates:
        doc_id = meta.get("doc_id", "unknown")
        trust = meta.get("trust", 1.0)

        # Limit to max 3 chunks per document for diversity
        if doc_chunk_count.get(doc_id, 0) >= 3:
            continue

        # Combine base score with trust
        final_score = base_score * trust
        reranked.append((chunk, meta, final_score))
        doc_chunk_count[doc_id] = doc_chunk_count.get(doc_id, 0) + 1

    reranked.sort(key=lambda x: -x[2])
    return reranked[:5]

def is_answerable(candidates: list, threshold: float = 0.3) -> bool:
    """Check if retrieved chunks are confident enough to answer."""
    if not candidates:
        return False
    top_score = candidates[0][2]
    return top_score >= threshold

def retrieve(query: str) -> dict:
    """
    Full retrieval pipeline for a query.
    Returns top chunks, their metadata, and whether the query is answerable.
    """
    candidates = hybrid_search(query)
    reranked = rerank(query, candidates)
    answerable = is_answerable(reranked)

    return {
        "answerable": answerable,
        "chunks": [c[0] for c in reranked],
        "metadatas": [c[1] for c in reranked],
        "scores": [c[2] for c in reranked]
    }