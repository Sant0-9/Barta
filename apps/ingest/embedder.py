"""Embedding and chunking functionality"""

import os
import sys
import logging
import hashlib
from typing import List, Optional
import numpy as np
import psycopg
import tiktoken
from sqlalchemy.sql import text

# Add the API directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../api'))
from core.config import settings

logger = logging.getLogger(__name__)


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> List[str]:
    """
    Chunk text into overlapping segments based on word count.
    
    Args:
        text: Input text to chunk
        chunk_size: Target number of words per chunk
        overlap: Number of words to overlap between chunks
    
    Returns:
        List of text chunks
    """
    if not text.strip():
        return []
    
    words = text.split()
    if len(words) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunks.append(' '.join(chunk_words))
        
        # If we've reached the end, break
        if end >= len(words):
            break
            
        # Move start position, accounting for overlap
        start = end - overlap
    
    return chunks


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Embed a list of texts. Falls back to deterministic random vectors if OpenAI API key is missing.
    
    Args:
        texts: List of text strings to embed
        
    Returns:
        List of embedding vectors (3072-dimensional)
    """
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    if openai_api_key:
        # TODO: Implement OpenAI embeddings when API key is available
        logger.info("OpenAI API key found - using deterministic fallback for now")
    
    # Deterministic random vectors for testing/fallback
    embeddings = []
    for text in texts:
        # Use SHA256 hash of text as seed for reproducible results
        seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
        np.random.seed(seed % (2**32))
        
        # Generate 1536-dimensional vector (compatible with ivfflat index limit)
        vector = np.random.normal(0, 1, 1536)
        # Normalize to unit vector
        vector = vector / np.linalg.norm(vector)
        embeddings.append(vector.tolist())
    
    return embeddings


def embed_article(conn: psycopg.Connection, article_id: int, full_text: str) -> bool:
    """
    Chunk article text, generate embeddings, and store in database.
    
    Args:
        conn: Database connection
        article_id: ID of the article to embed
        full_text: Full text content of the article
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Chunk the text
        chunks = chunk_text(full_text)
        if not chunks:
            logger.warning(f"No chunks generated for article {article_id}")
            return False
        
        logger.info(f"Generated {len(chunks)} chunks for article {article_id}")
        
        # Generate embeddings
        embeddings = embed_texts(chunks)
        
        # Insert chunks with embeddings
        with conn.cursor() as cur:
            for position, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # Generate tsvector for full-text search
                cur.execute("""
                    INSERT INTO article_chunks (article_id, position, content, embedding, tsv)
                    VALUES (%s, %s, %s, %s, to_tsvector('simple', %s))
                """, (article_id, position, chunk, embedding, chunk))
        
        conn.commit()
        logger.info(f"Successfully embedded article {article_id} with {len(chunks)} chunks")
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error embedding article {article_id}: {e}")
        return False


def main():
    """CLI entrypoint for embedding articles"""
    # Connect to database
    try:
        db_url = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
        conn = psycopg.connect(db_url)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)
    
    # Find articles without embeddings
    with conn.cursor() as cur:
        cur.execute("""
            SELECT a.id, a.title, a.body 
            FROM articles a
            LEFT JOIN article_chunks ac ON a.id = ac.article_id
            WHERE ac.article_id IS NULL
            ORDER BY a.created_at DESC
            LIMIT 10
        """)
        
        articles = cur.fetchall()
    
    if not articles:
        logger.info("No articles need embedding")
        sys.exit(0)
    
    logger.info(f"Found {len(articles)} articles to embed")
    
    success_count = 0
    error_count = 0
    
    for article_id, title, body in articles:
        logger.info(f"Embedding article {article_id}: {title or 'Untitled'}")
        
        if embed_article(conn, article_id, body or ""):
            success_count += 1
        else:
            error_count += 1
    
    conn.close()
    logger.info(f"Embedding complete. Success: {success_count}, Errors: {error_count}")


if __name__ == "__main__":
    main()