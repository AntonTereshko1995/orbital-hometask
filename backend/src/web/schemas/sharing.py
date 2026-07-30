from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from web.schemas.conversation import DocumentInfo


class SharedMessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    sources_cited: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SharedConversationOut(BaseModel):
    title: str
    created_at: datetime
    documents: list[DocumentInfo]
    messages: list[SharedMessageOut]
