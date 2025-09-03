"""Backfill tsv values for existing chunks

Revision ID: 002
Revises: 001
Create Date: 2025-09-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill any NULL tsv values
    op.execute("UPDATE article_chunks SET tsv = to_tsvector('simple', content) WHERE tsv IS NULL")
    
    # Ensure required indexes exist (should already exist from migration 001)
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunks_vec ON article_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists=200)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON article_chunks USING GIN(tsv)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_articles_url_hash ON articles (url_hash)")


def downgrade() -> None:
    # No downgrade needed for backfill
    pass