from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.message import Message
from db.repository import BaseRepository


class MessageRepository(BaseRepository[Message]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Message)

    async def list_for_conversation(self, conversation_id: str) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_history(self, conversation_id: str, exclude_id: str) -> list[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .where(Message.id != exclude_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())
