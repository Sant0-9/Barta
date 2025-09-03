"""Shared embedding client for both ingestion and retrieval"""

import os
import logging
import hashlib
from typing import List
import numpy as np

logger = logging.getLogger(__name__)

def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Embed a list of texts using OpenAI or deterministic fallback.
    
    Args:
        texts: List of text strings to embed
        
    Returns:
        List of embedding vectors (3072-dimensional for text-embedding-3-large)
    """
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    if openai_api_key:
        try:
            return _embed_with_openai(texts, openai_api_key)
        except Exception as e:
            logger.warning(f"OpenAI embedding failed: {e}, falling back to deterministic vectors")
            return _embed_deterministic(texts)
    else:
        logger.info("No OpenAI API key found, using deterministic vectors")
        return _embed_deterministic(texts)


def _embed_with_openai(texts: List[str], api_key: str) -> List[List[float]]:
    """Embed texts using OpenAI API"""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        response = client.embeddings.create(
            input=texts,
            model="text-embedding-3-large",  # 3072 dimensions as per requirements
        )
        
        embeddings = [item.embedding for item in response.data]
        logger.info(f"Successfully embedded {len(texts)} texts using OpenAI")
        return embeddings
        
    except ImportError:
        logger.warning("OpenAI package not available, using deterministic fallback")
        return _embed_deterministic(texts)
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise


def _embed_deterministic(texts: List[str]) -> List[List[float]]:
    """Generate deterministic pseudo-vectors based on text content"""
    embeddings = []
    
    for text in texts:
        if not text.strip():
            # Empty text gets zero vector
            embeddings.append([0.0] * 3072)
            continue
            
        # Use SHA256 hash of text as seed for reproducible results
        seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
        np.random.seed(seed % (2**32))
        
        # Generate 3072-dimensional vector (compatible with text-embedding-3-large)
        vector = np.random.normal(0, 1, 3072)
        
        # Normalize to unit vector
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
            
        embeddings.append(vector.tolist())
    
    logger.info(f"Generated {len(texts)} deterministic embeddings")
    return embeddings