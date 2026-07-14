from __future__ import annotations

from typing import TYPE_CHECKING

from db.models.base import Base
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from db.models.conversation import Conversation


class Document(Base):
    __tablename__ = "documents"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column()
    file_path: Mapped[str] = mapped_column()
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)

    conversation: Mapped[Conversation] = relationship(back_populates="documents")
