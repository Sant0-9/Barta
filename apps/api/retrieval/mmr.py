"""Maximal Marginal Relevance (MMR) implementation for diverse retrieval"""

import logging
from typing import List, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

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
    
    logger.info(f"MMR selected {len(selected)} candidates from {len(candidates)} with λ={lambda_}")
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