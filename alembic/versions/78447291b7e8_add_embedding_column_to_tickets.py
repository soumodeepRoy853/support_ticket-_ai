"""add embedding column to tickets

Revision ID: 78447291b7e8
Revises: aeae667bd3f3
Create Date: 2026-08-16 23:30:26.187351

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78447291b7e8'
down_revision: Union[str, None] = 'aeae667bd3f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
     op.execute("""
        CREATE INDEX ix_tickets_embedding
        ON tickets
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tickets_embedding")
