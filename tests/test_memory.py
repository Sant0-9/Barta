"""Tests for memory functionality"""

import os
import pytest
import tempfile
import sys
from unittest.mock import patch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Ensure OPENAI_API_KEY is not set for fallback tests
if 'OPENAI_API_KEY' in os.environ:
    del os.environ['OPENAI_API_KEY']

# Add project paths
sys.path.append(os.path.join(os.path.dirname(__file__), '../apps/api'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

# Set up test database URL
test_db_url = "sqlite:///test_memory.db"
os.environ['DATABASE_URL'] = test_db_url

from apps.api.memory.store import (
    start_conversation, append_message, get_recent_messages,
    get_summary, set_summary, conversation_exists
)
from apps.api.memory.summarize import summarize_short


@pytest.fixture
def test_db():
    """Create test database and session"""
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine)
    
    # Create tables
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS conversation_memory (
                conversation_id TEXT PRIMARY KEY,
                short_summary TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        """))
        
        conn.commit()
    
    session = SessionLocal()
    yield session
    session.close()
    
    # Clean up
    try:
        os.remove("test_memory.db")
    except FileNotFoundError:
        pass


def test_conversation_lifecycle(test_db):
    """Test creating conversations and adding messages"""
    # Start conversation
    conv_id = start_conversation(test_db)
    assert conv_id
    assert len(conv_id) > 8  # Should be a UUID-like string
    
    # Check conversation exists
    assert conversation_exists(test_db, conv_id)
    assert not conversation_exists(test_db, "nonexistent-id")
    
    # Add messages
    append_message(test_db, conv_id, "user", "Hello, what is climate change?")
    append_message(test_db, conv_id, "assistant", "Climate change refers to long-term changes in global temperatures.")
    
    # Get recent messages
    messages = get_recent_messages(test_db, conv_id, limit=5)
    assert len(messages) == 2
    assert messages[0]['role'] == 'user'
    assert messages[0]['content'] == "Hello, what is climate change?"
    assert messages[1]['role'] == 'assistant'
    
    print(f"✅ Conversation lifecycle works: {conv_id[:8]}...")


def test_conversation_summary(test_db):
    """Test conversation summarization"""
    # Create conversation with messages
    conv_id = start_conversation(test_db)
    
    append_message(test_db, conv_id, "user", "What are the causes of inflation in Bangladesh?")
    append_message(test_db, conv_id, "assistant", "Inflation in Bangladesh is caused by several factors including global commodity prices, supply chain disruptions, and monetary policy.")
    append_message(test_db, conv_id, "user", "How does this affect the common people?")
    append_message(test_db, conv_id, "assistant", "High inflation reduces purchasing power, making basic necessities more expensive for ordinary citizens.")
    
    # No summary initially
    summary = get_summary(test_db, conv_id)
    assert summary is None
    
    # Set summary
    set_summary(test_db, conv_id, "Discussion about Bangladesh inflation and its impact on citizens.")
    
    # Get summary
    summary = get_summary(test_db, conv_id)
    assert summary == "Discussion about Bangladesh inflation and its impact on citizens."
    
    # Update summary
    set_summary(test_db, conv_id, "Updated discussion about economic impacts.")
    updated_summary = get_summary(test_db, conv_id)
    assert updated_summary == "Updated discussion about economic impacts."
    
    print("✅ Summary storage and retrieval works")


def test_memory_summarization_fallback():
    """Test summarization when OPENAI_API_KEY is not available"""
    # Test messages
    messages = [
        {"role": "user", "content": "What is machine learning?"},
        {"role": "assistant", "content": "Machine learning is a subset of AI that enables computers to learn from data."},
        {"role": "user", "content": "How does it work?"},
        {"role": "assistant", "content": "It uses algorithms to find patterns in data and make predictions."}
    ]
    
    # Should work without API key
    summary = summarize_short(messages)
    
    # Should produce a reasonable summary
    assert len(summary) > 0
    assert len(summary) <= 200  # Should be short
    assert summary.count('\n') <= 1  # Should be 2 lines max
    
    print(f"✅ Fallback summarization works: '{summary}'")


def test_memory_summarization_edge_cases():
    """Test edge cases for summarization"""
    # Empty messages
    summary = summarize_short([])
    assert summary == ""
    
    # Single message
    messages = [{"role": "user", "content": "Hello"}]
    summary = summarize_short(messages)
    assert len(summary) > 0
    assert "Hello" in summary.lower() or "discussion" in summary.lower()
    
    # Only assistant messages
    messages = [{"role": "assistant", "content": "I can help you with that."}]
    summary = summarize_short(messages)
    assert len(summary) > 0
    
    print("✅ Edge cases handled correctly")


def test_message_limits(test_db):
    """Test message retrieval limits"""
    conv_id = start_conversation(test_db)
    
    # Add many messages
    for i in range(10):
        append_message(test_db, conv_id, "user", f"Message {i}")
        append_message(test_db, conv_id, "assistant", f"Response {i}")
    
    # Get limited messages
    recent_3 = get_recent_messages(test_db, conv_id, limit=3)
    assert len(recent_3) == 3
    
    # Should get the most recent ones
    assert "Message 9" in recent_3[1]['content']  # Most recent user message
    assert "Response 9" in recent_3[2]['content']  # Most recent assistant message
    
    # Get all messages
    all_messages = get_recent_messages(test_db, conv_id, limit=100)
    assert len(all_messages) == 20  # 10 user + 10 assistant
    
    print("✅ Message limits work correctly")


if __name__ == "__main__":
    # Create a test database session for standalone testing
    engine = create_engine("sqlite:///test_standalone.db")
    SessionLocal = sessionmaker(bind=engine)
    
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS conversation_memory (
                conversation_id TEXT PRIMARY KEY,
                short_summary TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
    
    test_db = SessionLocal()
    
    try:
        test_conversation_lifecycle(test_db)
        test_conversation_summary(test_db)
        test_memory_summarization_fallback()
        test_memory_summarization_edge_cases()
        test_message_limits(test_db)
        print("\n🎉 All memory tests passed!")
    finally:
        test_db.close()
        try:
            os.remove("test_standalone.db")
        except FileNotFoundError:
            pass