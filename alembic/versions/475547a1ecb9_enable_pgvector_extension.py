"""enable pgvector extension

Revision ID: 475547a1ecb9
Revises: 148ce819be41
Create Date: 2026-08-15 23:02:58.716981

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '475547a1ecb9'
down_revision: Union[str, None] = '148ce819be41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
