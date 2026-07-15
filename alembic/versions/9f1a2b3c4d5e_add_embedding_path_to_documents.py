"""add embedding_path to documents

Revision ID: 9f1a2b3c4d5e
Revises: 6e8841c9840a
Create Date: 2026-07-15 12:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9f1a2b3c4d5e'
down_revision: str | None = '6e8841c9840a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('embedding_path', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'embedding_path')
