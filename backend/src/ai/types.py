from __future__ import annotations

from typing import TypedDict


class SectionData(TypedDict):
    id: str
    doc_id: str
    index: int
    heading: str | None
    content: str
    token_count: int


class DocContext(TypedDict):
    id: str
    filename: str
    text: str
