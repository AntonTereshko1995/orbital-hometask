from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.document_section import DocumentSection
from db.repository import BaseRepository


class DocumentSectionRepository(BaseRepository[DocumentSection]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DocumentSection)

    async def list_for_document(self, document_id: str) -> list[DocumentSection]:
        result = await self._session.execute(
            select(DocumentSection)
            .where(DocumentSection.document_id == document_id)
            .order_by(DocumentSection.section_index.asc())
        )
        return list(result.scalars().all())

    async def save_bulk(self, instances: list[DocumentSection]) -> None:
        if not instances:
            return
        for instance in instances:
            self._session.add(instance)
        await self._session.commit()
