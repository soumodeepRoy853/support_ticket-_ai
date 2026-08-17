"""add ivfflat index on ticket embeddings

Revision ID: 620704bf0484
Revises: 78447291b7e8
Create Date: 2026-08-16 23:31:36.057946

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '620704bf0484'
down_revision: Union[str, None] = '78447291b7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
