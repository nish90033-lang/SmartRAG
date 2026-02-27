import chromadb
from chromadb.utils import embedding_functions
from rank_bm25 import BM25Okapi
import numpy as np

# Use chromadb's built-in lightweight embeddings (no PyTorch needed)
ef = embedding_functions.DefaultEmbeddingFunction()

# Initialize ChromaDB
chroma = chromadb.Client()
collection = chroma.get_or_create_collection("smartrag", embedding_function=ef)

# In-memory store for BM25
all_chunks = []
all_metadatas = []

def embed(text: str) -> list:
    return ef([text])[0]

def store_chunks(chunks: list, doc_id: str, trust_score: float):
    """Store chunks in batches."""
    global all_chunks, all_metadatas

    print(f"Storing {len(chunks)} chunks...")

    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    metadatas = [{"doc_id": doc_id, "trust": trust_score, "chunk_index": i} for i in range(len(chunks))]

    # Add in batches of 100
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        collection.add(
            documents=chunks[i:i+batch_size],
            ids=ids[i:i+batch_size],
            metadatas=metadatas[i:i+batch_size]
        )

    all_chunks.extend(chunks)
    all_metadatas.extend(metadatas)
    print(f"Stored {len(chunks)} chunks for doc '{doc_id}'")

def bm25_search(query: str, top_k: int = 10) -> list:
    if not all_chunks:
        return []
    tokenized_corpus = [c.split() for c in all_chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(query.split())
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [(all_chunks[i], all_metadatas[i], float(scores[i])) for i in top_indices]

def vector_search(query: str, top_k: int = 10) -> list:
    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count())
    )
    chunks = results['documents'][0]
    metadatas = results['metadatas'][0]
    distances = results['distances'][0]
    similarities = [1 / (1 + d) for d in distances]
    return list(zip(chunks, metadatas, similarities))

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

def is_answerable(candidates: list, threshold: float = 0.3) -> bool:
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