"""Convert documents to shared library with M:N conversation relationship

Revision ID: b2c3d4e5f6a7
Revises: 9f1a2b3c4d5e
Create Date: 2026-07-29 00:00:00.000000

Changes:
- Creates conversation_documents join table (M:N: conversations <-> documents)
- Migrates existing conversation_id data into the join table
- Adds file_size column to documents (for duplicate detection)
- Drops conversation_id column from documents
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "9f1a2b3c4d5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create the join table first (before dropping the FK from documents)
    op.create_table(
        "conversation_documents",
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("conversation_id", "document_id"),
    )

    # 2. Migrate existing conversation_id data into the join table
    op.execute(
        "INSERT INTO conversation_documents (conversation_id, document_id) "
        "SELECT conversation_id, id FROM documents WHERE conversation_id IS NOT NULL"
    )

    # 3. Add file_size column (default 0 for existing rows)
    op.add_column(
        "documents",
        sa.Column(
            "file_size",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # 4. Drop the FK constraint then the column
    op.drop_constraint("documents_conversation_id_fkey", "documents", type_="foreignkey")
    op.drop_column("documents", "conversation_id")


def downgrade() -> None:
    # Restore conversation_id column (nullable — some documents may have had multiple convs)
    op.add_column(
        "documents",
        sa.Column("conversation_id", sa.String(), nullable=True),
    )

    # Restore one conversation_id per document (take the earliest link)
    op.execute(
        "UPDATE documents d SET conversation_id = cd.conversation_id "
        "FROM ("
        "  SELECT DISTINCT ON (document_id) document_id, conversation_id "
        "  FROM conversation_documents "
        "  ORDER BY document_id, created_at ASC"
        ") cd "
        "WHERE cd.document_id = d.id"
    )

    op.create_foreign_key(
        "documents_conversation_id_fkey",
        "documents",
        "conversations",
        ["conversation_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_column("documents", "file_size")
    op.drop_table("conversation_documents")
