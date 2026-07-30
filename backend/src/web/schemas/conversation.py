from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator


class DocumentInfo(BaseModel):
    id: str
    filename: str
    file_size: int
    page_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationListItem(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    has_document: bool
    is_pinned: bool
    is_shared: bool
    share_token: str | None = None

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    has_document: bool
    is_pinned: bool
    is_shared: bool
    share_token: str | None = None
    documents: list[DocumentInfo] = []

    model_config = {"from_attributes": True}


class ConversationUpdate(BaseModel):
    title: str | None = None
    is_pinned: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> ConversationUpdate:
        if self.title is None and self.is_pinned is None:
            raise ValueError("at least one of title or is_pinned must be provided")
        return self


class ShareInfo(BaseModel):
    is_shared: bool
    share_token: str | None = None

    model_config = {"from_attributes": True}
