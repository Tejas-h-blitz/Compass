import os
import sys
from typing import Dict, Any, List, Optional
import chromadb
from sentence_transformers import SentenceTransformer

# Ensure import paths work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from backend.models.db import get_file_by_path

# Resolve paths
CHROMA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "chroma"))

# Singleton patterns for model and ChromaDB client.
# This prevents reloading the transformer model and re-opening database connections
# on every single search query, keeping response latency low.
_model = None
_chroma_client = None
_collection = None

def get_transformer_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # Tradeoff: 'all-MiniLM-L6-v2' is a lightweight embedding model (approx 90MB).
        # It is fast enough to run on CPU without requiring an external GPU/CUDA setup,
        # which fits our university project requirement of running locally and efficiently.
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def get_chroma_collection():
    global _chroma_client, _collection
    if _chroma_client is None:
        os.makedirs(CHROMA_DIR, exist_ok=True)
        # Using ChromaDB persistent local client. This avoids hosted vector DB costs/network delays,
        # perfectly matching our single-user offline local application architecture.
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
        # We explicitly configure the distance space as 'cosine'.
        # This bounds distance scores to [0, 2], making score normalization predictable.
        _collection = _chroma_client.get_or_create_collection(
            name="compass_files",
            metadata={"hnsw:space": "cosine"}
        )
    return _collection

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Splits document text into overlapping chunks.
    This guarantees that matches occurring across chunk boundaries are captured,
    and prevents large documents from exceeding the model's token limit.
    """
    if not text:
        return []
    
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end])
        if end == text_len:
            break
        # Slide window back by overlap amount to ensure continuity
        start += chunk_size - overlap
        
    return chunks

def upsert_file_embeddings(filepath: str, filename: str, content: str):
    """
    Generates embeddings for all text chunks of a file and indexes them in ChromaDB.
    Always cleans up existing chunks for the file first to prevent duplicate entries.
    """
    collection = get_chroma_collection()
    model = get_transformer_model()
    
    # 1. Purge existing chunks for this specific file path to prevent stale indices
    collection.delete(where={"filepath": filepath})
    
    # 2. Chunk text and generate embeddings
    chunks = chunk_text(content)
    if not chunks:
        return
        
    embeddings = model.encode(chunks).tolist()
    
    # 3. Insert new chunks
    ids = [f"{filepath}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "filepath": filepath,
            "filename": filename,
            "chunk_idx": i
        } for i in range(len(chunks))
    ]
    
    collection.add(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=chunks
    )

def delete_file_embeddings(filepath: str):
    """
    Removes all indexed vector chunks for a specific file path.
    """
    collection = get_chroma_collection()
    collection.delete(where={"filepath": filepath})

def semantic_search(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Performs vector search in ChromaDB.
    Retrieves matching chunks, groups them by file path, and aggregates their scores.
    """
    collection = get_chroma_collection()
    model = get_transformer_model()
    
    # Convert query into vector representation
    query_embedding = model.encode([query]).tolist()[0]
    
    # Query ChromaDB. We request more results than our output limit
    # because a single file might have multiple matching chunks.
    raw_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(limit * 3, 100),
        include=["documents", "metadatas", "distances"]
    )
    
    if not raw_results or not raw_results["ids"] or not raw_results["ids"][0]:
        return []
        
    ids = raw_results["ids"][0]
    distances = raw_results["distances"][0]
    metadatas = raw_results["metadatas"][0]
    documents = raw_results["documents"][0]
    
    # Group results by file path
    # We aggregate multi-chunk match scores by taking the maximum similarity score.
    # We also keep the chunk text of the highest-scoring match to explain the result.
    file_matches: Dict[str, Dict[str, Any]] = {}
    
    for i in range(len(ids)):
        meta = metadatas[i]
        filepath = meta["filepath"]
        filename = meta["filename"]
        distance = distances[i]
        chunk_text_content = documents[i]
        
        # Convert cosine distance to cosine similarity score.
        # Since 'cosine' distance = 1 - similarity:
        # similarity = 1 - distance. We clamp it at 0.0 to prevent negative values.
        similarity = max(0.0, 1.0 - distance)
        
        if filepath not in file_matches:
            file_matches[filepath] = {
                "filepath": filepath,
                "filename": filename,
                "raw_score": similarity,
                "best_chunk": chunk_text_content,
                "strategy": "semantic"
            }
        else:
            # If we found a chunk from the same file with a higher match score, update it
            if similarity > file_matches[filepath]["raw_score"]:
                file_matches[filepath]["raw_score"] = similarity
                file_matches[filepath]["best_chunk"] = chunk_text_content
                
    # Convert matches back to list
    results = list(file_matches.values())
    
    # Sort files by similarity score descending
    results.sort(key=lambda x: x["raw_score"], reverse=True)
    
    # Enrich matches with metadata from SQLite and set score field
    final_results = []
    for r in results[:limit]:
        db_file = get_file_by_path(r["filepath"])
        if db_file:
            final_results.append({
                "id": db_file["id"],
                "filepath": db_file["filepath"],
                "filename": db_file["filename"],
                "file_type": db_file["file_type"],
                "file_size": db_file["file_size"],
                "created_at": db_file["created_at"],
                "modified_at": db_file["modified_at"],
                "raw_score": r["raw_score"],
                "score": round(r["raw_score"], 4), # Cosine similarity is already normalized in [0, 1]
                "content_preview": r["best_chunk"][:200] + "..." if len(r["best_chunk"]) > 200 else r["best_chunk"],
                "strategy": "semantic"
            })
            
    return final_results
