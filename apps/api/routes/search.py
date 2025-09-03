"""Search API endpoints with Prometheus metrics"""

import time
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from prometheus_client import Histogram, Counter
from retrieval.retrieve import hybrid_search

logger = logging.getLogger(__name__)

# Prometheus metrics
retrieval_latency_histogram = Histogram(
    'retrieval_latency_ms',
    'Retrieval latency in milliseconds',
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
)

retrieval_queries_counter = Counter(
    'retrieval_queries_total',
    'Total number of retrieval queries'
)

reranker_cache_hits_counter = Counter(
    'reranker_cache_hits_total',
    'Total number of reranker cache hits'
)

reranker_cache_misses_counter = Counter(
    'reranker_cache_misses_total',
    'Total number of reranker cache misses'
)

# Router
search_router = APIRouter(prefix="/api", tags=["search"])

class SearchResult(BaseModel):
    chunk_id: int
    article_id: int
    title: str
    url: str
    published_at: str = None
    source_domain: str
    content: str
    score: float
    rerank_score: float

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]

@search_router.get("/search", response_model=SearchResponse)
async def search_articles(
    q: str = Query(..., description="Search query", min_length=1, max_length=256)
):
    """
    Search articles using hybrid retrieval (BM25 + dense vector search).
    
    Applies MMR for diversity and cross-encoder reranking for relevance.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Record query
    retrieval_queries_counter.inc()
    
    # Measure latency
    start_time = time.time()
    
    try:
        # Perform hybrid search
        results = hybrid_search(q)
        
        # Convert to response format
        search_results = []
        for result in results:
            search_results.append(SearchResult(
                chunk_id=result["chunk_id"],
                article_id=result["article_id"],
                title=result.get("title", ""),
                url=result.get("url", ""),
                published_at=result.get("published_at").isoformat() if result.get("published_at") else None,
                source_domain=result.get("source_domain", ""),
                content=result["content"],
                score=result.get("score", 0.0),
                rerank_score=result.get("rerank_score", 0.0)
            ))
        
        response = SearchResponse(query=q, results=search_results)
        
        # Record latency
        latency_ms = (time.time() - start_time) * 1000
        retrieval_latency_histogram.observe(latency_ms)
        
        logger.info(f"Search completed in {latency_ms:.1f}ms: '{q}' -> {len(results)} results")
        
        return response
        
    except Exception as e:
        logger.error(f"Search failed for query '{q}': {e}")
        raise HTTPException(status_code=500, detail="Search failed")


# Export metrics counters for use by reranker
def increment_cache_hits():
    """Increment cache hits counter (called by reranker)"""
    reranker_cache_hits_counter.inc()

def increment_cache_misses():
    """Increment cache misses counter (called by reranker)"""
    reranker_cache_misses_counter.inc()