"""Tests for chat fallback when OPENAI_API_KEY is missing"""

import os
import pytest
from fastapi.testclient import TestClient
import tempfile
import sys

# Ensure OPENAI_API_KEY is not set for these tests
if 'OPENAI_API_KEY' in os.environ:
    del os.environ['OPENAI_API_KEY']

# Add project paths
sys.path.append(os.path.join(os.path.dirname(__file__), '../apps/api'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from apps.api.main import app

client = TestClient(app)


def test_chat_fallback_without_api_key():
    """Test that chat endpoint works without OPENAI_API_KEY"""
    # Ensure no API key is set
    assert not os.getenv('OPENAI_API_KEY'), "OPENAI_API_KEY should not be set for this test"
    
    # Send a chat request
    response = client.post("/ask", json={
        "message": "What is happening in tech today?"
    })
    
    # Should return 200 with SSE stream
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    
    # Read the SSE events
    content = response.text
    lines = content.strip().split('\n')
    
    # Should have at least some events
    assert len(lines) > 0
    
    # Check for delta events
    delta_events = [line for line in lines if line.startswith('event: delta')]
    assert len(delta_events) >= 3, f"Expected at least 3 delta events, got {len(delta_events)}"
    
    # Check for done event
    done_events = [line for line in lines if line.startswith('event: done')]
    assert len(done_events) == 1, f"Expected exactly 1 done event, got {len(done_events)}"
    
    print(f"✅ Received {len(delta_events)} delta events and {len(done_events)} done event")


def test_chat_response_structure():
    """Test that chat response has proper SSE structure"""
    response = client.post("/ask", json={
        "message": "Tell me about climate change"
    })
    
    assert response.status_code == 200
    
    content = response.text
    lines = content.strip().split('\n')
    
    # Parse events
    events = []
    i = 0
    while i < len(lines):
        if lines[i].startswith('event: '):
            event_type = lines[i][7:]  # Remove "event: "
            if i + 1 < len(lines) and lines[i + 1].startswith('data: '):
                try:
                    import json
                    data = json.loads(lines[i + 1][6:])  # Remove "data: "
                    events.append({"type": event_type, "data": data})
                except json.JSONDecodeError:
                    pass
        i += 1
    
    # Should have at least delta and done events
    delta_events = [e for e in events if e["type"] == "delta"]
    done_events = [e for e in events if e["type"] == "done"]
    
    assert len(delta_events) >= 1, "Should have at least 1 delta event"
    assert len(done_events) == 1, "Should have exactly 1 done event"
    
    # Check done event structure
    done_event = done_events[0]
    assert "ok" in done_event["data"]
    assert "conversation_id" in done_event["data"]
    assert "sources" in done_event["data"]
    
    print(f"✅ Event structure is correct: {len(delta_events)} deltas, 1 done event")


def test_chat_validation():
    """Test chat input validation"""
    # Empty message
    response = client.post("/ask", json={"message": ""})
    assert response.status_code == 422
    
    # Missing message
    response = client.post("/ask", json={})
    assert response.status_code == 422
    
    # Message too long
    long_message = "a" * 2001
    response = client.post("/ask", json={"message": long_message})
    assert response.status_code == 422
    
    print("✅ Input validation works correctly")


def test_fake_streaming_deterministic():
    """Test that fake streaming produces reasonable content"""
    response = client.post("/ask", json={
        "message": "What is artificial intelligence?"
    })
    
    assert response.status_code == 200
    
    # Collect all tokens
    content = response.text
    lines = content.strip().split('\n')
    
    full_response = ""
    for line in lines:
        if line.startswith('data: '):
            try:
                import json
                data = json.loads(line[6:])
                if 'token' in data:
                    full_response += data['token']
            except json.JSONDecodeError:
                pass
    
    # Should produce a reasonable response with sections
    assert len(full_response) > 50, "Response should be substantial"
    assert "TL;DR" in full_response or "## " in full_response, "Should have structured sections"
    
    print(f"✅ Generated response ({len(full_response)} chars): {full_response[:100]}...")


if __name__ == "__main__":
    test_chat_fallback_without_api_key()
    test_chat_response_structure()
    test_chat_validation()
    test_fake_streaming_deterministic()
    print("\n🎉 All chat fallback tests passed!")