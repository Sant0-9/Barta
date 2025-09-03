"""Add ingestion tables

Revision ID: 001
Revises: 
Create Date: 2025-09-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable required extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    
    # Articles table
    op.create_table(
        'articles',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('url', sa.Text, nullable=False),
        sa.Column('url_hash', sa.LargeBinary, nullable=False),
        sa.Column('title', sa.Text),
        sa.Column('body', sa.Text),
        sa.Column('published_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('simhash', sa.BigInteger),
        sa.Column('source_domain', sa.Text),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    
    # Create unique indexes on articles
    op.create_index('idx_articles_url', 'articles', ['url'], unique=True)
    op.create_index('idx_articles_url_hash', 'articles', ['url_hash'], unique=True)
    op.create_index('idx_articles_simhash', 'articles', ['simhash'])
    op.create_index('idx_articles_created_at', 'articles', ['created_at'])
    
    # Article chunks table with vector column
    op.create_table(
        'article_chunks',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('article_id', sa.BigInteger, sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer, nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('embedding', postgresql.ARRAY(sa.Float), nullable=True),  # Will be converted to vector via raw SQL
        sa.Column('tsv', postgresql.TSVECTOR)
    )
    
    # Convert embedding column to vector type (1536 dimensions for compatibility with ivfflat)
    op.execute("ALTER TABLE article_chunks ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector")
    
    # Create indexes on article_chunks
    op.create_index('idx_chunks_article_id', 'article_chunks', ['article_id'])
    op.create_index('idx_chunks_position', 'article_chunks', ['article_id', 'position'])
    
    # Vector index (will be created with proper data) - ivfflat supports up to 2000 dimensions
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunks_vec ON article_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists=200)")
    
    # Full-text search index
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON article_chunks USING GIN(tsv)")
    
    # Conversations table
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    
    # Messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('conversation_id', postgresql.UUID, sa.ForeignKey('conversations.id'), nullable=False),
        sa.Column('role', sa.Text, nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    
    # Add check constraint for role
    op.execute("ALTER TABLE messages ADD CONSTRAINT chk_messages_role CHECK (role IN ('user', 'assistant', 'tool'))")
    
    # Conversation memory table
    op.create_table(
        'conversation_memory',
        sa.Column('conversation_id', postgresql.UUID, sa.ForeignKey('conversations.id'), primary_key=True),
        sa.Column('short_summary', sa.Text),
        sa.Column('last_updated', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    
    # Create indexes for conversations and messages
    op.create_index('idx_messages_conversation_id', 'messages', ['conversation_id'])
    op.create_index('idx_messages_created_at', 'messages', ['created_at'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('conversation_memory')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('article_chunks')
    op.drop_table('articles')
    
    # Note: We don't drop extensions as they might be used by other parts