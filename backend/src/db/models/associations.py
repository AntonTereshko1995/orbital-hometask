from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func

from db.models.base import Base

# Many-to-many join table between conversations and documents.
# A document can be shared across multiple conversations without duplication.
# Defined here (not in conversation.py or document.py) to avoid circular imports.
conversation_documents = Table(
    "conversation_documents",
    Base.metadata,
    Column(
        "conversation_id",
        String,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "document_id",
        String,
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("created_at", DateTime, server_default=func.now()),
)
