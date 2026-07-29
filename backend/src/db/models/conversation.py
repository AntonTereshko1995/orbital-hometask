from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.associations import conversation_documents
from db.models.base import Base

if TYPE_CHECKING:
    from db.models.document import Document
    from db.models.message import Message


class Conversation(Base):
    __tablename__ = "conversations"

    title: Mapped[str] = mapped_column(default="New Conversation")

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    documents: Mapped[list[Document]] = relationship(
        "Document",
        secondary=conversation_documents,
        back_populates="conversations",
    )
