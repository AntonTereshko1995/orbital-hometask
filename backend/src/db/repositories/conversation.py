from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models.conversation import Conversation
from db.repository import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Conversation)

    async def get(self, id: str) -> Conversation | None:
        result = await self._session.execute(
            select(Conversation)
            .options(selectinload(Conversation.documents))
            .where(Conversation.id == id)
        )
        return result.scalar_one_or_none()

    async def list(self) -> list[Conversation]:
        result = await self._session.execute(
            select(Conversation)
            .options(selectinload(Conversation.documents))
            .order_by(Conversation.is_pinned.desc(), Conversation.updated_at.desc())
        )
        return list(result.scalars().all())

    async def update_title(self, id: str, title: str) -> Conversation | None:
        conversation = await self.get(id)
        if conversation is None:
            return None
        conversation.title = title
        return await self.save(conversation)

    async def update_pin(self, id: str, is_pinned: bool) -> Conversation | None:
        conversation = await self.get(id)
        if conversation is None:
            return None
        conversation.is_pinned = is_pinned
        return await self.save(conversation)

    async def get_by_share_token(self, token: str) -> Conversation | None:
        result = await self._session.execute(
            select(Conversation)
            .options(selectinload(Conversation.documents))
            .where(Conversation.share_token == token, Conversation.is_shared == True)  # noqa: E712
        )
        return result.scalar_one_or_none()

    async def enable_share(self, id: str) -> Conversation | None:
        conversation = await self.get(id)
        if conversation is None:
            return None
        if conversation.share_token is None:
            conversation.share_token = uuid.uuid4().hex
        conversation.is_shared = True
        return await self.save(conversation)

    async def disable_share(self, id: str) -> bool:
        conversation = await self.get(id)
        if conversation is None:
            return False
        conversation.is_shared = False
        await self.save(conversation)
        return True
