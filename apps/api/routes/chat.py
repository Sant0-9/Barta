"""Chat API endpoints with SSE streaming"""

import json
import time
import logging
import os
import sys
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session
from prometheus_client import Histogram, Counter

# Import LLM module
try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))
    from packages.shared.llm import stream_chat, complete
except ImportError:
    from shared.llm import stream_chat, complete

from core.config import settings
from core.db import get_db
from memory.store import (
    start_conversation, append_message, get_recent_messages,
    get_summary, set_summary, conversation_exists
)
from memory.summarize import summarize_short
from retrieval.retrieve import hybrid_search, format_passages

logger = logging.getLogger(__name__)

# Prometheus metrics
llm_latency_histogram = Histogram(
    'llm_latency_ms',
    'LLM response latency in milliseconds',
    buckets=[100, 250, 500, 1000, 2000, 5000, 10000]
)

answers_streamed_counter = Counter(
    'answers_streamed_total',
    'Total number of answers streamed'
)

# Router
chat_router = APIRouter(prefix="", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    
    @validator('message')
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError('Message cannot be empty')
        if len(v) > 2000:
            raise ValueError('Message too long (max 2000 characters)')
        return v.strip()


def _load_prompt_template(filename: str) -> str:
    """Load prompt template from file"""
    try:
        # Try local prompts first, then fallback to packages
        local_path = os.path.join(os.path.dirname(__file__), '../shared/prompts', filename)
        packages_path = os.path.join(os.path.dirname(__file__), '../../../packages/shared/prompts', filename)
        
        template_path = local_path if os.path.exists(local_path) else packages_path
        with open(template_path, 'r') as f:
            content = f.read().strip()
        
        # Replace template variables
        content = content.replace('{{PLAN_MAX_BULLETS}}', str(settings.PLAN_MAX_BULLETS))
        return content
    except Exception as e:
        logger.error(f"Failed to load prompt template {filename}: {e}")
        return f"Template {filename} not found"


def _format_sse_event(event: str, data: Dict[str, Any]) -> str:
    """Format Server-Sent Event"""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _has_proper_citations(text: str) -> bool:
    """Check if text has proper citations"""
    has_brackets = '[' in text and ']' in text
    has_sources_section = 'sources' in text.lower()
    return has_brackets and has_sources_section


async def _generate_chat_stream(
    request: ChatRequest, 
    db: Session
):
    """Generate chat response stream"""
    try:
        # Step 1: Setup conversation with error recovery
        conversation_id = None
        try:
            if request.conversation_id and conversation_exists(db, request.conversation_id):
                conversation_id = request.conversation_id
                logger.info(f"Using existing conversation: {conversation_id}")
            else:
                conversation_id = start_conversation(db)
                logger.info(f"Started new conversation: {conversation_id}")
        except Exception as e:
            logger.error(f"Conversation setup failed: {e}")
            # Create fresh database session and retry
            db.rollback()
            try:
                conversation_id = start_conversation(db)
                logger.info(f"Started new conversation after error recovery: {conversation_id}")
            except Exception as retry_e:
                logger.error(f"Failed to recover conversation setup: {retry_e}")
                raise Exception("Unable to setup conversation. Please try again.")
        
        # Step 2: Get conversation context
        summary = get_summary(db, conversation_id) or "(none)"
        logger.debug(f"Conversation summary: {summary[:100]}...")
        
        # Step 3: Retrieval pass - get relevant passages
        logger.info(f"Starting retrieval for query: {request.message[:50]}...")
        passages = hybrid_search(request.message)
        formatted_passages, sources_list = format_passages(passages)
        
        logger.info(f"Retrieved {len(passages)} passages")
        
        # Step 4: Pass 1 - Planning
        logger.info("Starting planning pass...")
        system_prompt = _load_prompt_template('system.txt')
        plan_prompt = _load_prompt_template('plan.txt')
        
        plan_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""Query: {request.message}

Conversation summary:
{summary}

Passages:
{formatted_passages}"""},
            {"role": "assistant", "content": "OK, I will produce a plan."},
            {"role": "user", "content": plan_prompt}
        ]
        
        plan = complete(
            plan_messages,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=200
        )
        
        logger.info(f"Generated plan: {plan[:100]}...")
        
        # Step 5: Pass 2 - Answer (streaming)
        logger.info("Starting answer pass with streaming...")
        answer_prompt = _load_prompt_template('answer.txt')
        
        answer_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""Query: {request.message}

Conversation summary:
{summary}

Passages:
{formatted_passages}

Plan:
{plan}

Now write the final answer using the required sections and inline citations."""}
        ]
        
        # Stream the response
        start_time = time.time()
        final_text = ""
        
        try:
            for token in stream_chat(
                answer_messages,
                model=settings.LLM_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS
            ):
                final_text += token
                yield _format_sse_event("delta", {"token": token})
            
            # Record latency
            latency_ms = (time.time() - start_time) * 1000
            llm_latency_histogram.observe(latency_ms)
            
            logger.info(f"Streaming completed in {latency_ms:.1f}ms")
            
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield _format_sse_event("error", {"message": f"Streaming failed: {str(e)}"})
            return
        
        # Step 6: Citation enforcement
        if settings.CITATION_STRICT and passages:
            if not _has_proper_citations(final_text):
                logger.warning("Response lacks proper citations, retrying...")
                
                # Retry with stronger instruction
                retry_messages = answer_messages + [
                    {"role": "assistant", "content": final_text},
                    {"role": "user", "content": "Your first attempt lacked proper citations. Try again and include inline [1],[2],... markers with a Sources section."}
                ]
                
                retry_text = ""
                for token in stream_chat(
                    retry_messages,
                    model=settings.LLM_MODEL,
                    temperature=settings.LLM_TEMPERATURE,
                    max_tokens=settings.LLM_MAX_TOKENS
                ):
                    retry_text += token
                    yield _format_sse_event("delta", {"token": token})
                
                final_text = retry_text
                logger.info("Retry completed with better citations")
        
        # Step 7: Persistence with transaction handling
        logger.info("Persisting conversation...")
        
        try:
            # Save messages
            append_message(db, conversation_id, "user", request.message)
            append_message(db, conversation_id, "assistant", final_text)
            
            # Update summary
            recent_messages = get_recent_messages(db, conversation_id, limit=8)
            if len(recent_messages) > 2:  # Only summarize if we have enough history
                new_summary = summarize_short(recent_messages)
                set_summary(db, conversation_id, new_summary)
                logger.debug(f"Updated summary: {new_summary}")
                
        except Exception as persist_e:
            logger.error(f"Failed to persist conversation: {persist_e}")
            db.rollback()
            # Continue anyway - the response was already generated successfully
        
        # Step 8: Final event with metadata
        answers_streamed_counter.inc()
        
        yield _format_sse_event("done", {
            "ok": True,
            "conversation_id": conversation_id,
            "sources": sources_list
        })
        
        logger.info(f"Chat response completed for conversation {conversation_id}")
        
    except Exception as e:
        logger.error(f"Chat stream generation failed: {e}")
        yield _format_sse_event("error", {"message": f"Chat error: {str(e)}"})


@chat_router.post("/ask")
async def ask(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Ask a question and get a streaming response.
    
    Returns Server-Sent Events (SSE) stream with:
    - event: delta, data: {"token": "..."}  (for each response token)
    - event: done, data: {"ok": true, "conversation_id": "...", "sources": [...]}
    - event: error, data: {"message": "..."} (on error)
    """
    logger.info(f"Received chat request: {request.message[:100]}...")
    
    async def event_generator():
        async for event in _generate_chat_stream(request, db):
            yield event
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )