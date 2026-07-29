from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


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

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    has_document: bool
    documents: list[DocumentInfo] = []

    model_config = {"from_attributes": True}


class ConversationUpdate(BaseModel):
    title: str
