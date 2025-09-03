"""Memory summarization functionality"""

import logging
import sys
import os
from typing import List, Dict, Any

# Import LLM module
try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))
    from packages.shared.llm import complete
except ImportError:
    from shared.llm import complete
from core.config import settings

logger = logging.getLogger(__name__)


def summarize_short(messages: List[Dict[str, Any]]) -> str:
    """
    Create a short summary of conversation messages.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        
    Returns:
        str: Short summary (2 lines max)
    """
    if not messages:
        return ""
    
    # If only one exchange, create a simple summary
    if len(messages) <= 2:
        return _create_simple_summary(messages)
    
    # Try to use LLM if API key is available
    try:
        return _create_llm_summary(messages)
    except Exception as e:
        logger.warning(f"LLM summarization failed: {e}, using fallback")
        return _create_fallback_summary(messages)


def _create_llm_summary(messages: List[Dict[str, Any]]) -> str:
    """Create summary using LLM"""
    # Build conversation text
    conversation_text = "\n\n".join([
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in messages[-6:]  # Last 6 messages to avoid token limits
    ])
    
    # Summarization prompt
    llm_messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that creates very brief conversation summaries."
        },
        {
            "role": "user",
            "content": f"""Summarize this conversation in 1-2 short sentences. Focus on the main topics discussed and key information exchanged.

Conversation:
{conversation_text}

Summary:"""
        }
    ]
    
    # Get summary from LLM
    summary = complete(
        llm_messages,
        model=settings.LLM_MODEL,
        temperature=0.1,  # Low temperature for consistent summaries
        max_tokens=100    # Short summary
    )
    
    # Clean and limit the summary
    summary = summary.strip()
    lines = [line.strip() for line in summary.split('\n') if line.strip()]
    
    # Return first 2 lines or first 200 chars, whichever is shorter
    if len(lines) <= 2:
        result = '\n'.join(lines)
    else:
        result = '\n'.join(lines[:2])
    
    if len(result) > 200:
        result = result[:197] + "..."
    
    logger.info("Created LLM-based conversation summary")
    return result


def _create_fallback_summary(messages: List[Dict[str, Any]]) -> str:
    """Create fallback summary when LLM is unavailable"""
    if not messages:
        return "No conversation history"
    
    # Get last user and assistant messages
    last_user_msg = ""
    last_assistant_msg = ""
    
    for msg in reversed(messages):
        if msg['role'] == 'user' and not last_user_msg:
            last_user_msg = msg['content'][:100]
        elif msg['role'] == 'assistant' and not last_assistant_msg:
            last_assistant_msg = msg['content'][:100]
        
        if last_user_msg and last_assistant_msg:
            break
    
    # Create simple summary
    parts = []
    if last_user_msg:
        # Extract key terms from user message
        user_summary = _extract_key_terms(last_user_msg)
        parts.append(f"User asked about {user_summary}")
    
    if last_assistant_msg:
        # Determine response type
        if "sources" in last_assistant_msg.lower() or "[" in last_assistant_msg:
            parts.append("Assistant provided analysis with sources")
        else:
            parts.append("Assistant provided information")
    
    if not parts:
        parts = [f"Conversation with {len(messages)} messages"]
    
    result = ". ".join(parts) + "."
    logger.info("Created fallback conversation summary")
    return result


def _create_simple_summary(messages: List[Dict[str, Any]]) -> str:
    """Create simple summary for short conversations"""
    if not messages:
        return ""
    
    # Find the user message
    user_content = ""
    for msg in messages:
        if msg['role'] == 'user':
            user_content = msg['content']
            break
    
    if user_content:
        key_terms = _extract_key_terms(user_content)
        return f"Discussion about {key_terms}"
    else:
        return "New conversation started"


def _extract_key_terms(text: str) -> str:
    """Extract key terms from text"""
    # Remove common stop words and extract meaningful terms
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'about', 'what', 'how', 'when', 'where', 'why', 'who', 'which', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'}
    
    # Clean and split text
    words = text.lower().replace('?', '').replace('.', '').replace(',', '').split()
    
    # Filter out stop words and short words
    key_words = [word for word in words if len(word) > 3 and word not in stop_words]
    
    # Take first few meaningful words
    if key_words:
        return " ".join(key_words[:3])
    else:
        # Fallback to first few words
        first_words = text.split()[:3]
        return " ".join(first_words)