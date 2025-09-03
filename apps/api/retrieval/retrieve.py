"""Hybrid retrieval pipeline combining BM25 and dense vector search"""

import logging
import sys
import os
from typing import List, Dict, Any
import numpy as np
from sqlalchemy import create_engine, text
from core.config import settings
from .mmr import mmr
from .rerank import get_reranker

# Import embedding module
try:
    # Try to import from packages first
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))
    from packages.shared.embedding import embed_texts
except ImportError:
    # Fallback to local shared module
    from shared.embedding import embed_texts

logger = logging.getLogger(__name__)

# Database engine for retrieval
engine = create_engine(settings.DATABASE_URL)

def bm25_search(query: str, limit: int) -> List[Dict[str, Any]]:
    """
    Perform BM25 search using PostgreSQL full-text search.
    
    Args:
        query: Search query text
        limit: Maximum number of results to return
        
    Returns:
        List of dictionaries with chunk and article metadata
    """
    sql = """
    SELECT 
        ac.id as chunk_id,
        ac.article_id,
        ac.position,
        ac.content,
        ac.embedding,
        ts_rank(ac.tsv, plainto_tsquery('simple', :query)) as score,
        a.title,
        a.url,
        a.published_at,
        a.source_domain
    FROM article_chunks ac
    JOIN articles a ON ac.article_id = a.id
    WHERE ac.tsv @@ plainto_tsquery('simple', :query)
    ORDER BY score DESC
    LIMIT :limit
    """
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), {"query": query, "limit": limit})
            rows = result.fetchall()
            
        candidates = []
        for row in rows:
            candidates.append({
                "chunk_id": row.chunk_id,
                "article_id": row.article_id,
                "position": row.position,
                "content": row.content,
                "embedding": row.embedding,
                "score": float(row.score),
                "title": row.title,
                "url": row.url,
                "published_at": row.published_at,
                "source_domain": row.source_domain,
                "source": "bm25"
            })
        
        logger.info(f"BM25 search found {len(candidates)} candidates for query: {query[:50]}...")
        return candidates
        
    except Exception as e:
        logger.error(f"BM25 search failed: {e}")
        return []


def dense_search(query_vec: List[float], limit: int) -> List[Dict[str, Any]]:
    """
    Perform dense vector search using pgvector.
    
    Args:
        query_vec: Query embedding vector
        limit: Maximum number of results to return
        
    Returns:
        List of dictionaries with chunk and article metadata
    """
    sql = """
    SELECT 
        ac.id as chunk_id,
        ac.article_id,
        ac.position,
        ac.content,
        ac.embedding,
        1 - (ac.embedding <=> :query_vec) as score,
        a.title,
        a.url,
        a.published_at,
        a.source_domain
    FROM article_chunks ac
    JOIN articles a ON ac.article_id = a.id
    WHERE ac.embedding IS NOT NULL
    ORDER BY ac.embedding <=> :query_vec
    LIMIT :limit
    """
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), {"query_vec": query_vec, "limit": limit})
            rows = result.fetchall()
    except Exception as e:
        logger.error(f"Dense vector search failed: {e}")
        return []  # Return empty results on error
        
    candidates = []
    for row in rows:
        candidates.append({
            "chunk_id": row.chunk_id,
            "article_id": row.article_id,
            "position": row.position,
            "content": row.content,
            "embedding": row.embedding,
            "score": float(row.score),
            "title": row.title,
            "url": row.url,
            "published_at": row.published_at,
            "source_domain": row.source_domain,
            "source": "dense"
        })
        
    logger.info(f"Dense search found {len(candidates)} candidates")
    return candidates


def _normalize_scores(candidates: List[Dict[str, Any]], source_key: str) -> List[Dict[str, Any]]:
    """Normalize scores to 0-1 range using min-max scaling"""
    source_candidates = [c for c in candidates if c["source"] == source_key]
    
    if not source_candidates:
        return candidates
    
    scores = [c["score"] for c in source_candidates]
    min_score = min(scores)
    max_score = max(scores)
    
    # Avoid division by zero
    if max_score == min_score:
        for candidate in source_candidates:
            candidate["score"] = 1.0
    else:
        for candidate in source_candidates:
            candidate["score"] = (candidate["score"] - min_score) / (max_score - min_score)
    
    return candidates


def _merge_candidates(bm25_results: List[Dict[str, Any]], 
                     dense_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge BM25 and dense search results, handling duplicates"""
    # Normalize scores separately for each method
    all_candidates = bm25_results + dense_results
    all_candidates = _normalize_scores(all_candidates, "bm25")
    all_candidates = _normalize_scores(all_candidates, "dense")
    
    # Merge duplicates by chunk_id, keeping the higher score
    merged = {}
    for candidate in all_candidates:
        chunk_id = candidate["chunk_id"]
        
        if chunk_id in merged:
            # Keep higher score and mark as both sources
            if candidate["score"] > merged[chunk_id]["score"]:
                merged[chunk_id] = candidate
            merged[chunk_id]["source"] = "both"
        else:
            merged[chunk_id] = candidate
    
    return list(merged.values())


def hybrid_search(query: str) -> List[Dict[str, Any]]:
    """
    Perform hybrid retrieval combining BM25 and dense search with MMR and reranking.
    
    Args:
        query: Search query text
        
    Returns:
        List of final ranked passages
    """
    if not query.strip():
        return []
    
    logger.info(f"Starting hybrid search for: {query[:100]}...")
    
    # Step 1: Get query embedding
    try:
        query_embeddings = embed_texts([query])
        query_vec = query_embeddings[0]
        query_vec_np = np.array(query_vec)
    except Exception as e:
        logger.error(f"Failed to embed query: {e}")
        return []
    
    # Step 2: Perform BM25 and dense search
    bm25_results = bm25_search(query, settings.RETRIEVAL_K_BM25)
    dense_results = dense_search(query_vec, settings.RETRIEVAL_K_DENSE)
    
    # Step 3: Merge and deduplicate candidates
    merged_candidates = _merge_candidates(bm25_results, dense_results)
    
    if not merged_candidates:
        logger.info("No candidates found")
        return []
    
    # Step 4: Prepare candidates for MMR (ensure vectors are numpy arrays)
    for candidate in merged_candidates:
        if candidate["embedding"]:
            candidate["vec"] = np.array(candidate["embedding"])
        else:
            # Fallback to zero vector if no embedding
            candidate["vec"] = np.zeros(len(query_vec))
    
    # Step 5: Apply MMR for diversity
    mmr_candidates = mmr(
        merged_candidates, 
        query_vec_np, 
        settings.RETRIEVAL_MMR_LAMBDA, 
        settings.RETRIEVAL_MMR_K
    )
    
    logger.info(f"MMR selected {len(mmr_candidates)} candidates")
    
    # Step 6: Apply reranking
    reranker = get_reranker()
    reranked_candidates = reranker.rerank(query, mmr_candidates)
    
    # Step 7: Take top K results
    final_results = reranked_candidates[:settings.RETRIEVAL_FINAL_K]
    
    # Clean up results (remove internal fields)
    for result in final_results:
        result.pop("vec", None)
        result.pop("embedding", None)
    
    logger.info(f"Hybrid search returned {len(final_results)} final results")
    return final_results


def format_passages(passages: List[Dict[str, Any]]) -> tuple[str, List[Dict[str, Any]]]:
    """
    Format passages for use in LLM prompts and return sources for citations.
    
    Args:
        passages: List of passage dictionaries from hybrid_search
        
    Returns:
        Tuple of (formatted_text_block, numbered_sources_list)
        - formatted_text_block: String formatted for LLM prompt with [1], [2], etc.
        - numbered_sources_list: List of source dicts for citation output
    """
    if not passages:
        return "No relevant passages found.", []
    
    formatted_lines = []
    sources_list = []
    
    for i, passage in enumerate(passages, 1):
        # Extract metadata
        title = passage.get('title', 'Untitled')
        source_domain = passage.get('source_domain', 'unknown')
        published_at = passage.get('published_at', '')
        url = passage.get('url', '')
        content = passage.get('content', '')
        
        # Format published date
        if published_at:
            try:
                if hasattr(published_at, 'strftime'):
                    date_str = published_at.strftime('%Y-%m-%d')
                else:
                    date_str = str(published_at)[:10]  # Take first 10 chars (YYYY-MM-DD)
            except:
                date_str = 'recent'
        else:
            date_str = 'recent'
        
        # Truncate content for prompt (keep it manageable)
        content_snippet = content[:400] + "..." if len(content) > 400 else content
        
        # Format for prompt
        formatted_lines.append(
            f"[{i}] {title} ({source_domain}, {date_str}) — {content_snippet}"
        )
        
        # Add to sources list for citation output
        sources_list.append({
            "index": i,
            "title": title,
            "url": url,
            "source_domain": source_domain,
            "published_at": published_at.isoformat() if hasattr(published_at, 'isoformat') else str(published_at) if published_at else None
        })
    
    formatted_text = "\n\n".join(formatted_lines)
    
    logger.info(f"Formatted {len(passages)} passages for LLM prompt")
    return formatted_text, sources_list