from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.base import Base


class BaseRepository[ModelT: Base]:
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self._session = session
        self._model = model

    async def get(self, id: str) -> ModelT | None:
        result = await self._session.execute(select(self._model).where(self._model.id == id))
        return result.scalar_one_or_none()

    async def list(self) -> list[ModelT]:
        result = await self._session.execute(select(self._model))
        return list(result.scalars().all())

    async def save(self, instance: ModelT) -> ModelT:
        self._session.add(instance)
        await self._session.commit()
        await self._session.refresh(instance)
        return instance

    async def delete(self, id: str) -> bool:
        instance = await self.get(id)
        if instance is None:
            return False
        await self._session.delete(instance)
        await self._session.commit()
        return True
