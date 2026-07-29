from __future__ import annotations

import structlog
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import DocumentRepository
from db.session import get_session
from services.document import upload_to_library
from web.schemas.document import DocumentOut

logger = structlog.get_logger()

router = APIRouter(prefix="/api/storage", tags=["storage"])


async def get_document_repo(
    session: AsyncSession = Depends(get_session),
) -> DocumentRepository:
    return DocumentRepository(session)


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_to_library_endpoint(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
) -> DocumentOut:
    """Upload a PDF directly to the library without attaching it to a conversation.

    If the same file (filename + size) already exists in the library the existing
    document is returned with reused_from_library=True and no file is written.
    """
    try:
        document, is_duplicate = await upload_to_library(session, file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    logger.info(
        "Document uploaded to library",
        document_id=document.id,
        filename=document.filename,
        is_duplicate=is_duplicate,
    )

    return DocumentOut(
        id=document.id,
        filename=document.filename,
        file_size=document.file_size,
        page_count=document.page_count,
        created_at=document.created_at,
        reused_from_library=is_duplicate,
    )


@router.get("", response_model=list[DocumentOut])
async def list_library(
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repo)],
) -> list[DocumentOut]:
    """List all documents in the library, ordered by most recently added."""
    docs = await doc_repo.list()
    # Sort by created_at descending (BaseRepository.list() has no ordering)
    docs.sort(key=lambda d: d.created_at, reverse=True)
    return [
        DocumentOut(
            id=d.id,
            filename=d.filename,
            file_size=d.file_size,
            page_count=d.page_count,
            created_at=d.created_at,
        )
        for d in docs
    ]
