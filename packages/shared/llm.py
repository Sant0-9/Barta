"""Shared LLM client with streaming support and graceful fallback"""

import os
import logging
import time
from typing import Iterator, List, Dict, Any
import hashlib

logger = logging.getLogger(__name__)
# Force reload for API key fix - testing integration


def stream_chat(messages: List[Dict[str, str]], *, model: str, temperature: float, max_tokens: int) -> Iterator[str]:
    """
    Stream chat completion tokens.
    
    Args:
        messages: List of message dicts with 'role' and 'content' keys
        model: Model name (e.g., 'gpt-4o-mini')
        temperature: Temperature parameter
        max_tokens: Maximum tokens to generate
        
    Yields:
        str: Individual tokens from the response
    """
    # Try to load from .env file if not already set
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        try:
            # Try to read from project root .env file
            env_path = os.path.join(os.path.dirname(__file__), '../../../.env')
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    for line in f:
                        if line.startswith('OPENAI_API_KEY='):
                            openai_api_key = line.split('=', 1)[1].strip()
                            logger.info("Loaded OpenAI API key from .env file")
                            break
        except Exception as e:
            logger.warning(f"Could not load .env file: {e}")
    
    if openai_api_key:
        try:
            yield from _stream_openai(messages, model, temperature, max_tokens, openai_api_key)
        except Exception as e:
            logger.warning(f"OpenAI streaming failed: {e}, falling back to fake stream")
            yield from _fake_stream(messages)
    else:
        logger.info("No OpenAI API key found, using fake stream")
        yield from _fake_stream(messages)


def complete(messages: List[Dict[str, str]], *, model: str, temperature: float, max_tokens: int) -> str:
    """
    Complete chat completion (non-streaming).
    
    Args:
        messages: List of message dicts with 'role' and 'content' keys
        model: Model name (e.g., 'gpt-4o-mini')
        temperature: Temperature parameter
        max_tokens: Maximum tokens to generate
        
    Returns:
        str: Complete response text
    """
    # Try to load from .env file if not already set
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        try:
            # Try to read from project root .env file
            env_path = os.path.join(os.path.dirname(__file__), '../../../.env')
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    for line in f:
                        if line.startswith('OPENAI_API_KEY='):
                            openai_api_key = line.split('=', 1)[1].strip()
                            logger.info("Loaded OpenAI API key from .env file")
                            break
        except Exception as e:
            logger.warning(f"Could not load .env file: {e}")
    
    if openai_api_key:
        try:
            return _complete_openai(messages, model, temperature, max_tokens, openai_api_key)
        except Exception as e:
            logger.warning(f"OpenAI completion failed: {e}, falling back to fake completion")
            return _fake_complete(messages)
    else:
        logger.info("No OpenAI API key found, using fake completion")
        return _fake_complete(messages)


def _stream_openai(messages: List[Dict[str, str]], model: str, temperature: float, max_tokens: int, api_key: str) -> Iterator[str]:
    """Stream tokens from OpenAI API"""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        
        for chunk in stream:
            try:
                if hasattr(chunk, 'choices') and chunk.choices:
                    choice = chunk.choices[0]
                    if hasattr(choice, 'delta') and hasattr(choice.delta, 'content'):
                        content = choice.delta.content
                        if content is not None and isinstance(content, str):
                            yield content
            except (AttributeError, IndexError, TypeError) as chunk_error:
                logger.warning(f"Skipping malformed chunk in OpenAI stream: {chunk_error}")
                continue
                
        logger.info(f"Successfully streamed response from OpenAI model {model}")
        
    except ImportError:
        logger.warning("OpenAI package not available, using fake stream")
        yield from _fake_stream(messages)
    except Exception as e:
        logger.error(f"OpenAI streaming error: {e}")
        raise


def _complete_openai(messages: List[Dict[str, str]], model: str, temperature: float, max_tokens: int, api_key: str) -> str:
    """Get complete response from OpenAI API"""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        content = response.choices[0].message.content
        logger.info(f"Successfully completed response from OpenAI model {model}")
        return content or ""
        
    except ImportError:
        logger.warning("OpenAI package not available, using fake completion")
        return _fake_complete(messages)
    except Exception as e:
        logger.error(f"OpenAI completion error: {e}")
        raise


def _fake_stream(messages: List[Dict[str, str]]) -> Iterator[str]:
    """Generate a deterministic fake stream for development"""
    # Create deterministic response based on last user message
    last_user_message = ""
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            last_user_message = msg.get('content', '')
            break
    
    # Generate deterministic response based on hash of input
    seed = hashlib.sha256(last_user_message.encode()).hexdigest()[:8]
    
    # Simulate a realistic response
    response_parts = [
        "## TL;DR\n\n",
        f"Based on the query '{last_user_message[:50]}...', here's a summary of key findings.\n\n",
        "## What happened\n\n",
        "Recent developments indicate ongoing changes in the situation. ",
        "Multiple sources report significant activity in the area [1]. ",
        "Key stakeholders have provided statements [2].\n\n",
        "## Why it matters\n\n",
        "This development has implications for future policy decisions. ",
        "The impact extends beyond immediate concerns [3].\n\n",
        "## Unknowns\n\n",
        "Several questions remain unanswered about long-term effects.\n\n",
        "## Timeline\n\n",
        "- Recent: Initial reports emerged\n",
        "- Current: Ongoing assessment\n",
        "- Future: Further developments expected\n\n",
        "## Sources\n\n",
        "[1] Example Source 1 (example.com)\n",
        "[2] Example Source 2 (news.example.com)\n",
        "[3] Example Source 3 (analysis.example.com)\n"
    ]
    
    # Stream the parts with realistic delays
    for part in response_parts:
        yield part
        time.sleep(0.1)  # Simulate network delay
    
    logger.info("Generated fake streaming response")


def _fake_complete(messages: List[Dict[str, str]]) -> str:
    """Generate a deterministic fake completion for development"""
    # For planning or summary tasks, return a simple response
    last_user_message = ""
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            last_user_message = msg.get('content', '')
            break
    
    if "plan" in last_user_message.lower():
        return """• Analyze the query and available information
• Identify key facts and developments
• Determine significance and implications
• Note any gaps or unknowns
• Structure findings clearly"""
    elif "summarize" in last_user_message.lower():
        return "Previous discussion covered recent developments and their implications for stakeholders."
    else:
        return "I understand your request and will provide a comprehensive response based on available information."