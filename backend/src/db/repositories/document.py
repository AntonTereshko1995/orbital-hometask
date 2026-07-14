from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.document import Document
from db.repository import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Document)

    async def get_for_conversation(self, conversation_id: str) -> Document | None:
        result = await self._session.execute(
            select(Document).where(Document.conversation_id == conversation_id)
        )
        return result.scalar_one_or_none()
