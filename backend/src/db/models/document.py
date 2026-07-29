from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.associations import conversation_documents
from db.models.base import Base

if TYPE_CHECKING:
    from db.models.conversation import Conversation
    from db.models.document_section import DocumentSection


class Document(Base):
    __tablename__ = "documents"

    filename: Mapped[str] = mapped_column()
    file_path: Mapped[str] = mapped_column()
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str | None] = mapped_column(nullable=True, index=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_path: Mapped[str | None] = mapped_column(nullable=True)

    conversations: Mapped[list[Conversation]] = relationship(
        "Conversation",
        secondary=conversation_documents,
        back_populates="documents",
    )
    sections: Mapped[list[DocumentSection]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
