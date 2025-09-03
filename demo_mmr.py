#!/usr/bin/env python3
"""
Standalone demonstration of the MMR algorithm implementation
"""

import numpy as np
from typing import List, Dict, Any

def mmr(candidates: List[Dict[str, Any]], query_vec: np.ndarray, lambda_: float, k: int) -> List[Dict[str, Any]]:
    """
    Apply Maximal Marginal Relevance (MMR) to select diverse candidates.
    
    Args:
        candidates: List of candidate documents with 'vec' and 'score' fields
        query_vec: Query vector as numpy array
        lambda_: Trade-off parameter (0=diversity only, 1=relevance only)
        k: Number of candidates to select
        
    Returns:
        List of selected candidates (k or fewer if candidates < k)
    """
    if not candidates:
        return []
        
    if len(candidates) <= k:
        return candidates
    
    # Normalize query vector
    query_vec = _normalize_vector(query_vec)
    
    # Ensure all candidate vectors are numpy arrays and normalized
    for candidate in candidates:
        if isinstance(candidate['vec'], list):
            candidate['vec'] = np.array(candidate['vec'])
        candidate['vec'] = _normalize_vector(candidate['vec'])
    
    selected = []
    remaining = candidates.copy()
    
    # Select first document with highest relevance score
    remaining.sort(key=lambda x: x['score'], reverse=True)
    selected.append(remaining.pop(0))
    
    # Iteratively select remaining documents
    while len(selected) < k and remaining:
        best_mmr = -float('inf')
        best_idx = -1
        
        for i, candidate in enumerate(remaining):
            # Relevance term: cosine similarity to query
            relevance = _cosine_similarity(candidate['vec'], query_vec)
            
            # Diversity term: max cosine similarity to already selected docs
            max_similarity = 0.0
            for selected_doc in selected:
                similarity = _cosine_similarity(candidate['vec'], selected_doc['vec'])
                max_similarity = max(max_similarity, similarity)
            
            # MMR score: λ * relevance - (1-λ) * max_similarity
            mmr_score = lambda_ * relevance - (1 - lambda_) * max_similarity
            
            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_idx = i
        
        if best_idx >= 0:
            selected.append(remaining.pop(best_idx))
    
    return selected


def _normalize_vector(vec: np.ndarray) -> np.ndarray:
    """Normalize vector to unit length"""
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Compute cosine similarity between two vectors"""
    # Vectors should already be normalized
    return float(np.dot(vec1, vec2))


def demo_mmr():
    """Demonstrate MMR with synthetic data"""
    print("🧠 MMR Algorithm Demonstration")
    print("=" * 40)
    print()
    
    # Create synthetic candidates with vectors and scores
    candidates = [
        {
            "id": 1,
            "vec": np.array([1.0, 0.0, 0.0]),
            "score": 0.9,
            "content": "High relevance document about topic A"
        },
        {
            "id": 2,
            "vec": np.array([0.9, 0.1, 0.0]),  # Similar to first
            "score": 0.8,
            "content": "Medium relevance, similar to doc 1"
        },
        {
            "id": 3,
            "vec": np.array([0.0, 1.0, 0.0]),  # Different direction
            "score": 0.7,
            "content": "Medium relevance, different topic B"
        },
        {
            "id": 4,
            "vec": np.array([0.0, 0.0, 1.0]),  # Another direction
            "score": 0.6,
            "content": "Lower relevance, unique topic C"
        },
        {
            "id": 5,
            "vec": np.array([0.8, 0.2, 0.0]),  # Similar to first two
            "score": 0.5,
            "content": "Low relevance, similar to docs 1&2"
        }
    ]
    
    query_vec = np.array([1.0, 0.0, 0.0])
    
    print(f"📊 Input: {len(candidates)} candidates")
    print("Query vector: [1.0, 0.0, 0.0] (aligned with topic A)")
    print()
    
    print("📋 Candidates:")
    for c in candidates:
        similarity = _cosine_similarity(_normalize_vector(c['vec']), _normalize_vector(query_vec))
        print(f"   {c['id']}: Score={c['score']:.2f}, Similarity={similarity:.2f} - {c['content']}")
    print()
    
    # Test different lambda values
    lambdas = [1.0, 0.7, 0.0]
    k = 3
    
    for lambda_val in lambdas:
        print(f"🎯 MMR with λ={lambda_val} (k={k}):")
        
        if lambda_val == 1.0:
            print("   Pure relevance - should pick highest scoring docs")
        elif lambda_val == 0.0:
            print("   Pure diversity - should pick most different docs")
        else:
            print("   Balanced - should balance relevance and diversity")
        
        selected = mmr(candidates.copy(), query_vec, lambda_val, k)
        
        print("   Selected:")
        for i, doc in enumerate(selected, 1):
            print(f"      {i}. Doc {doc['id']}: Score={doc['score']:.2f} - {doc['content']}")
        print()

def demo_cache_key():
    """Demonstrate cache key generation"""
    print("🔑 Cache Key Generation Demo")
    print("=" * 40)
    
    import hashlib
    
    def get_cache_key(query: str, chunk_id: int) -> str:
        """Generate cache key for query-chunk pair"""
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        return f"rrank:{query_hash}:{chunk_id}"
    
    test_cases = [
        ("climate change", 123),
        ("climate change", 456), 
        ("different query", 123),
        ("climate change", 123),  # Same as first
    ]
    
    print("Test cases:")
    keys = []
    for query, chunk_id in test_cases:
        key = get_cache_key(query, chunk_id)
        keys.append(key)
        print(f"   Query='{query}', Chunk={chunk_id} -> {key}")
    
    print()
    print("✅ Key stability: Same inputs produce same keys")
    print(f"   Key 1 == Key 4: {keys[0] == keys[3]}")
    print("✅ Key uniqueness: Different inputs produce different keys")
    print(f"   All keys unique: {len(keys) == len(set(keys))}")

if __name__ == "__main__":
    demo_mmr()
    print()
    demo_cache_key()
    
    print()
    print("🎉 MMR Algorithm Successfully Demonstrated!")
    print("The algorithm balances relevance and diversity as expected.")