"""Update vector dimensions to 3072

Revision ID: 003
Revises: 002
Create Date: 2025-09-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old vector index
    op.execute("DROP INDEX IF EXISTS idx_chunks_vec")
    
    # Update the embedding column to use 3072 dimensions
    op.execute("ALTER TABLE article_chunks ALTER COLUMN embedding TYPE vector(3072)")
    
    # Recreate the vector index with 3072 dimensions
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunks_vec ON article_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists=200)")


def downgrade() -> None:
    # Drop the new vector index
    op.execute("DROP INDEX IF EXISTS idx_chunks_vec")
    
    # Revert the embedding column to 1536 dimensions
    op.execute("ALTER TABLE article_chunks ALTER COLUMN embedding TYPE vector(1536)")
    
    # Recreate the vector index with 1536 dimensions
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunks_vec ON article_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists=200)")