from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    filename: str
    file_size: int
    page_count: int
    created_at: datetime
    reused_from_library: bool = False

    model_config = {"from_attributes": True}


class AttachFromLibraryRequest(BaseModel):
    document_id: str
