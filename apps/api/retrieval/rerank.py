"""Cross-encoder reranking with Redis caching"""

import logging
import hashlib
from typing import List, Dict, Any, Optional
import redis
from core.config import settings

logger = logging.getLogger(__name__)

class Reranker:
    """Cross-encoder reranker with Redis caching"""
    
    def __init__(self):
        self.enabled = settings.RERANKER_ENABLED
        self.model = None
        self.redis_client = None
        self.cache_ttl = settings.CACHE_TTL_SECONDS
        
        if self.enabled:
            self._init_model()
            self._init_redis()
    
    def _init_model(self):
        """Initialize the cross-encoder model"""
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(settings.RERANKER_MODEL)
            logger.info(f"Loaded reranker model: {settings.RERANKER_MODEL}")
        except ImportError as e:
            logger.warning(f"sentence-transformers not available: {e}. Reranking disabled.")
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to load reranker model: {e}. Reranking disabled.")
            self.enabled = False
    
    def _init_redis(self):
        """Initialize Redis connection for caching"""
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL)
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connection established for reranker caching")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            self.redis_client = None
    
    def rerank(self, query: str, passages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rerank passages using cross-encoder model with Redis caching.
        
        Args:
            query: Search query text
            passages: List of passage dicts with 'chunk_id', 'content', and other fields
            
        Returns:
            List of passages with added 'rerank_score' field, sorted by rerank_score desc
        """
        if not self.enabled or not passages:
            # If reranking disabled, use existing score as rerank_score
            for passage in passages:
                passage['rerank_score'] = passage.get('score', 0.0)
            return sorted(passages, key=lambda x: x.get('score', 0), reverse=True)
        
        # Try to get cached scores
        cache_hits = 0
        cache_misses = 0
        uncached_passages = []
        
        for passage in passages:
            cached_score = self._get_cached_score(query, passage['chunk_id'])
            if cached_score is not None:
                passage['rerank_score'] = cached_score
                cache_hits += 1
            else:
                uncached_passages.append(passage)
                cache_misses += 1
        
        # Rerank uncached passages
        if uncached_passages and self.model:
            try:
                # Prepare query-passage pairs for the model
                pairs = [(query, passage['content']) for passage in uncached_passages]
                scores = self.model.predict(pairs)
                
                # Assign scores and cache them
                for passage, score in zip(uncached_passages, scores):
                    passage['rerank_score'] = float(score)
                    self._cache_score(query, passage['chunk_id'], float(score))
                
                logger.info(f"Reranked {len(uncached_passages)} passages")
                
            except Exception as e:
                logger.error(f"Reranking failed: {e}. Using original scores.")
                for passage in uncached_passages:
                    passage['rerank_score'] = passage.get('score', 0.0)
        
        # Log and track cache performance
        if self.redis_client:
            logger.info(f"Reranker cache: {cache_hits} hits, {cache_misses} misses")
            
            # Update Prometheus metrics
            try:
                from routes.search import increment_cache_hits, increment_cache_misses
                for _ in range(cache_hits):
                    increment_cache_hits()
                for _ in range(cache_misses):
                    increment_cache_misses()
            except ImportError:
                pass  # Metrics not available
        
        # Sort by rerank_score descending
        return sorted(passages, key=lambda x: x['rerank_score'], reverse=True)
    
    def _get_cache_key(self, query: str, chunk_id: int) -> str:
        """Generate cache key for query-chunk pair"""
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        return f"rrank:{query_hash}:{chunk_id}"
    
    def _get_cached_score(self, query: str, chunk_id: int) -> Optional[float]:
        """Get cached rerank score"""
        if not self.redis_client:
            return None
        
        try:
            key = self._get_cache_key(query, chunk_id)
            cached = self.redis_client.get(key)
            if cached:
                return float(cached.decode())
        except Exception as e:
            logger.warning(f"Failed to get cached score: {e}")
        
        return None
    
    def _cache_score(self, query: str, chunk_id: int, score: float):
        """Cache rerank score"""
        if not self.redis_client:
            return
        
        try:
            key = self._get_cache_key(query, chunk_id)
            self.redis_client.setex(key, self.cache_ttl, str(score))
        except Exception as e:
            logger.warning(f"Failed to cache score: {e}")


# Global reranker instance
_reranker_instance = None

def get_reranker() -> Reranker:
    """Get singleton reranker instance"""
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = Reranker()
    return _reranker_instance