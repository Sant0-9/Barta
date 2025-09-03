"""Tests for ingestion pipeline functionality"""

import pytest
import sys
import os
from unittest.mock import patch

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from apps.ingest.embedder import chunk_text, embed_texts
    from apps.ingest.worker import compute_simhash
    from apps.ingest.utils import sha256_bytes, get_domain
except ImportError:
    # If running from container, adjust imports
    import sys
    sys.path.insert(0, '/app')
    from apps.ingest.embedder import chunk_text, embed_texts
    from apps.ingest.worker import compute_simhash
    from apps.ingest.utils import sha256_bytes, get_domain


def test_chunk_text_basic():
    """Test basic text chunking functionality"""
    text = "This is a test. " * 100  # 400 words
    chunks = chunk_text(text, chunk_size=50, overlap=10)
    
    assert len(chunks) > 1
    assert all(len(chunk.split()) <= 60 for chunk in chunks)  # Some tolerance


def test_chunk_text_overlap():
    """Test that chunks have proper overlap"""
    text = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10"
    chunks = chunk_text(text, chunk_size=5, overlap=2)
    
    # The chunking produces 3 chunks: [1-5], [4-8], [7-10]
    assert len(chunks) >= 2
    # Check that overlap exists between consecutive chunks
    assert "word4" in chunks[0] and "word4" in chunks[1]
    assert "word5" in chunks[0] and "word5" in chunks[1]


def test_chunk_text_short_text():
    """Test chunking of text shorter than chunk size"""
    text = "Short text"
    chunks = chunk_text(text, chunk_size=50)
    
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty():
    """Test chunking of empty text"""
    chunks = chunk_text("")
    assert len(chunks) == 0
    
    chunks = chunk_text("   ")
    assert len(chunks) == 0


@patch('apps.ingest.embedder.os.getenv')
def test_embed_texts_fallback(mock_getenv):
    """Test deterministic embedding fallback when no OpenAI key"""
    mock_getenv.return_value = None
    
    texts = ["Hello world", "Test text", "Another sample"]
    embeddings = embed_texts(texts)
    
    assert len(embeddings) == 3
    assert all(len(emb) == 1536 for emb in embeddings)
    
    # Test determinism - same text should produce same embedding
    embeddings2 = embed_texts(["Hello world"])
    assert embeddings[0] == embeddings2[0]


def test_compute_simhash_determinism():
    """Test that simhash is deterministic for same input"""
    text = "This is a test article about news and current events."
    
    hash1 = compute_simhash(text)
    hash2 = compute_simhash(text)
    
    assert hash1 == hash2
    assert isinstance(hash1, int)
    assert hash1 != 0


def test_compute_simhash_different_texts():
    """Test that different texts produce different simhashes"""
    text1 = "This is about technology and innovation."
    text2 = "This is about sports and athletics."
    
    hash1 = compute_simhash(text1)
    hash2 = compute_simhash(text2)
    
    assert hash1 != hash2


def test_compute_simhash_empty():
    """Test simhash with empty text"""
    assert compute_simhash("") == 0
    assert compute_simhash("   ") == 0


def test_sha256_bytes():
    """Test URL hash generation"""
    url = "https://example.com/test"
    hash_bytes = sha256_bytes(url)
    
    assert len(hash_bytes) == 32  # SHA256 produces 32 bytes
    assert isinstance(hash_bytes, bytes)
    
    # Same URL should produce same hash
    assert sha256_bytes(url) == sha256_bytes(url)
    
    # Different URLs should produce different hashes
    assert sha256_bytes(url) != sha256_bytes("https://example.com/other")


def test_get_domain():
    """Test domain extraction from URLs"""
    assert get_domain("https://example.com/path") == "example.com"
    assert get_domain("http://news.example.com/article/123") == "news.example.com"
    assert get_domain("https://EXAMPLE.COM/PATH") == "example.com"
    assert get_domain("https://sub.domain.example.co.uk/path") == "sub.domain.example.co.uk"


@pytest.mark.parametrize("chunk_size,overlap", [
    (800, 120),  # Default values
    (1000, 150),
    (500, 80),
])
def test_chunk_text_parameters(chunk_size, overlap):
    """Test chunking with different parameters"""
    # Create text with known word count
    words = ["word" + str(i) for i in range(2000)]
    text = " ".join(words)
    
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    
    # Should produce multiple chunks
    assert len(chunks) > 1
    
    # Each chunk should not exceed chunk_size (with some tolerance)
    for chunk in chunks:
        word_count = len(chunk.split())
        assert word_count <= chunk_size + overlap  # Allow for overlap tolerance