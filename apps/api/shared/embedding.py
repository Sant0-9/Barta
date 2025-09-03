"""Simple embedding module for API"""
import numpy as np
from typing import List

def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Simple fallback embedding function that returns deterministic vectors
    This is a placeholder until the packages/ directory is properly loaded
    """
    # Create deterministic embeddings based on text hash
    embeddings = []
    for text in texts:
        # Create a simple hash-based embedding (3072 dimensions for OpenAI compatibility)
        text_hash = hash(text)
        # Use the hash to create a deterministic vector
        np.random.seed(text_hash % 2**31)  # Ensure positive seed
        embedding = np.random.normal(0, 1, 3072)
        embedding = embedding / np.linalg.norm(embedding)  # Normalize
        embeddings.append(embedding)
    
    return np.array(embeddings)