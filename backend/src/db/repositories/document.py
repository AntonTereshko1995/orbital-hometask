from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.associations import conversation_documents
from db.models.document import Document
from db.repository import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Document)

    async def find_duplicate(self, content_hash: str) -> Document | None:
        """Return an existing document with the same SHA-256 content hash, or None."""
        result = await self._session.execute(
            select(Document).where(Document.content_hash == content_hash).limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_conversation(self, conversation_id: str) -> list[Document]:
        """Return all documents attached to a conversation, ordered by attachment time."""
        result = await self._session.execute(
            select(Document)
            .join(
                conversation_documents,
                Document.id == conversation_documents.c.document_id,
            )
            .where(conversation_documents.c.conversation_id == conversation_id)
            .order_by(conversation_documents.c.created_at.asc())
        )
        return list(result.scalars().all())

    async def attach_to_conversation(self, document_id: str, conversation_id: str) -> None:
        """Link a library document to a conversation (idempotent)."""
        existing = await self._session.execute(
            select(conversation_documents).where(
                conversation_documents.c.conversation_id == conversation_id,
                conversation_documents.c.document_id == document_id,
            )
        )
        if existing.first() is not None:
            return

        await self._session.execute(
            conversation_documents.insert().values(
                conversation_id=conversation_id,
                document_id=document_id,
            )
        )
        await self._session.commit()
