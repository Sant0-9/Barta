"""Tests for retrieval pipeline functionality"""

import pytest
from unittest.mock import patch, MagicMock
import numpy as np
import sys
import os

# Add project paths
sys.path.append(os.path.join(os.path.dirname(__file__), '../apps/api'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from apps.api.retrieval.mmr import mmr
from apps.api.retrieval.rerank import Reranker


def test_mmr_basic():
    """Test basic MMR functionality"""
    # Create synthetic candidates with vectors and scores
    candidates = [
        {
            "id": 1,
            "vec": np.array([1.0, 0.0, 0.0]),
            "score": 0.9,
            "content": "First document"
        },
        {
            "id": 2, 
            "vec": np.array([0.9, 0.1, 0.0]),  # Similar to first
            "score": 0.8,
            "content": "Second document"
        },
        {
            "id": 3,
            "vec": np.array([0.0, 1.0, 0.0]),  # Different direction
            "score": 0.7,
            "content": "Third document"
        },
        {
            "id": 4,
            "vec": np.array([0.0, 0.0, 1.0]),  # Another direction
            "score": 0.6,
            "content": "Fourth document"
        }
    ]
    
    query_vec = np.array([1.0, 0.0, 0.0])
    
    # Test with k=2, lambda=0.7 (favor relevance but consider diversity)
    selected = mmr(candidates, query_vec, lambda_=0.7, k=2)
    
    # Should return exactly 2 results
    assert len(selected) == 2
    
    # Should not have duplicates
    selected_ids = [doc["id"] for doc in selected]
    assert len(selected_ids) == len(set(selected_ids))
    
    # First should be highest relevance (id=1)
    assert selected[0]["id"] == 1
    
    # Second should prefer diversity over similarity
    # id=3 should be preferred over id=2 due to diversity
    assert selected[1]["id"] == 3


def test_mmr_edge_cases():
    """Test MMR edge cases"""
    # Empty candidates
    result = mmr([], np.array([1.0, 0.0]), lambda_=0.5, k=5)
    assert len(result) == 0
    
    # Fewer candidates than k
    candidates = [
        {"id": 1, "vec": np.array([1.0, 0.0]), "score": 0.8, "content": "doc1"}
    ]
    query_vec = np.array([1.0, 0.0])
    result = mmr(candidates, query_vec, lambda_=0.5, k=5)
    assert len(result) == 1
    assert result[0]["id"] == 1


def test_mmr_lambda_extremes():
    """Test MMR behavior with extreme lambda values"""
    candidates = [
        {"id": 1, "vec": np.array([1.0, 0.0]), "score": 0.9, "content": "high relevance"},
        {"id": 2, "vec": np.array([1.0, 0.0]), "score": 0.8, "content": "similar, lower relevance"},
        {"id": 3, "vec": np.array([0.0, 1.0]), "score": 0.5, "content": "diverse, low relevance"}
    ]
    query_vec = np.array([1.0, 0.0])
    
    # Lambda = 1 (pure relevance)
    result_relevance = mmr(candidates, query_vec, lambda_=1.0, k=2)
    assert result_relevance[0]["id"] == 1
    assert result_relevance[1]["id"] == 2  # Should pick similar doc due to pure relevance
    
    # Lambda = 0 (pure diversity) 
    result_diversity = mmr(candidates, query_vec, lambda_=0.0, k=2)
    assert result_diversity[0]["id"] == 1  # First is still highest score
    assert result_diversity[1]["id"] == 3  # Should pick diverse doc


def test_reranker_cache_key_stability():
    """Test that cache keys are stable for same query and chunk"""
    reranker = Reranker()
    
    query = "test query"
    chunk_id = 123
    
    key1 = reranker._get_cache_key(query, chunk_id)
    key2 = reranker._get_cache_key(query, chunk_id)
    
    # Same inputs should produce same key
    assert key1 == key2
    
    # Different inputs should produce different keys
    key3 = reranker._get_cache_key("different query", chunk_id)
    key4 = reranker._get_cache_key(query, 456)
    
    assert key1 != key3
    assert key1 != key4


def test_reranker_disabled():
    """Test reranker behavior when disabled"""
    with patch('apps.api.core.config.settings') as mock_settings:
        mock_settings.RERANKER_ENABLED = False
        
        reranker = Reranker()
        
        passages = [
            {"chunk_id": 1, "content": "test content 1", "score": 0.8},
            {"chunk_id": 2, "content": "test content 2", "score": 0.6}
        ]
        
        result = reranker.rerank("test query", passages)
        
        # Should return passages sorted by original score
        assert len(result) == 2
        assert result[0]["chunk_id"] == 1  # Higher score first
        assert result[0]["rerank_score"] == 0.8  # Uses original score
        assert result[1]["rerank_score"] == 0.6


@patch('apps.api.retrieval.retrieve.bm25_search')
@patch('apps.api.retrieval.retrieve.dense_search')
@patch('packages.shared.embedding.embed_texts')
def test_hybrid_search_integration_light(mock_embed, mock_dense, mock_bm25):
    """Integration test with mocked search functions"""
    from apps.api.retrieval.retrieve import hybrid_search
    
    # Mock embedding
    mock_embed.return_value = [[0.1, 0.2, 0.3] * 512]  # 1536-dim vector
    
    # Mock BM25 results
    mock_bm25.return_value = [
        {
            "chunk_id": 1,
            "article_id": 101,
            "content": "BM25 content 1",
            "score": 0.8,
            "title": "Article 1",
            "url": "http://example.com/1",
            "published_at": "2025-01-01",
            "source_domain": "example.com",
            "source": "bm25",
            "embedding": [0.1] * 1536
        },
        {
            "chunk_id": 2,
            "article_id": 102,
            "content": "BM25 content 2", 
            "score": 0.6,
            "title": "Article 2",
            "url": "http://example.com/2",
            "published_at": "2025-01-02",
            "source_domain": "example.com",
            "source": "bm25",
            "embedding": [0.2] * 1536
        }
    ]
    
    # Mock dense results (with some overlap)
    mock_dense.return_value = [
        {
            "chunk_id": 1,  # Same as BM25 result
            "article_id": 101,
            "content": "Dense content 1",
            "score": 0.9,
            "title": "Article 1", 
            "url": "http://example.com/1",
            "published_at": "2025-01-01",
            "source_domain": "example.com",
            "source": "dense",
            "embedding": [0.1] * 1536
        },
        {
            "chunk_id": 3,
            "article_id": 103, 
            "content": "Dense content 3",
            "score": 0.7,
            "title": "Article 3",
            "url": "http://example.com/3",
            "published_at": "2025-01-03",
            "source_domain": "example.com",
            "source": "dense",
            "embedding": [0.3] * 1536
        }
    ]
    
    with patch('apps.api.core.config.settings') as mock_settings:
        mock_settings.RETRIEVAL_K_BM25 = 100
        mock_settings.RETRIEVAL_K_DENSE = 100
        mock_settings.RETRIEVAL_MMR_K = 40
        mock_settings.RETRIEVAL_FINAL_K = 8
        mock_settings.RETRIEVAL_MMR_LAMBDA = 0.7
        mock_settings.RERANKER_ENABLED = False  # Disable reranker for deterministic results
        
        results = hybrid_search("test query")
        
        # Should have merged results (deduplicating chunk_id=1)
        assert len(results) <= 8  # Respects RETRIEVAL_FINAL_K
        
        # Should contain unique chunk_ids
        chunk_ids = [r["chunk_id"] for r in results]
        assert len(chunk_ids) == len(set(chunk_ids))
        
        # Should not contain internal fields
        for result in results:
            assert "vec" not in result
            assert "embedding" not in result
            assert "rerank_score" in result


def test_hybrid_search_empty_query():
    """Test hybrid search with empty query"""
    from apps.api.retrieval.retrieve import hybrid_search
    
    result = hybrid_search("")
    assert result == []
    
    result = hybrid_search("   ")
    assert result == []


if __name__ == "__main__":
    pytest.main([__file__])