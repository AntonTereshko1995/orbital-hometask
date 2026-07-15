from __future__ import annotations

import os
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import FileResponse

from db.repositories import ConversationRepository, DocumentRepository
from db.session import get_session
from services.document import upload_document
from web.schemas.document import DocumentOut

logger = structlog.get_logger()

router = APIRouter(tags=["documents"])


async def get_conversation_repo(
    session: AsyncSession = Depends(get_session),
) -> ConversationRepository:
    return ConversationRepository(session)


async def get_document_repo(
    session: AsyncSession = Depends(get_session),
) -> DocumentRepository:
    return DocumentRepository(session)


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@router.post(
    "/api/conversations/{conversation_id}/documents",
    response_model=DocumentOut,
    status_code=201,
)
async def upload_document_endpoint(
    conversation_id: str,
    file: UploadFile,
    conv_repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
    session: AsyncSession = Depends(get_session),
) -> DocumentOut:
    """Upload a PDF document for a conversation.

    Only one document per conversation is allowed. Returns 409 if a document
    already exists.
    """
    conversation = await conv_repo.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    try:
        document = await upload_document(session, conversation_id, file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    logger.info(
        "Document uploaded",
        conversation_id=conversation_id,
        document_id=document.id,
        filename=document.filename,
    )

    return DocumentOut(
        id=document.id,
        conversation_id=document.conversation_id,
        filename=document.filename,
        page_count=document.page_count,
        created_at=document.created_at,
    )


@router.get("/api/documents/{document_id}/content")
async def serve_document_file(
    document_id: str,
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repo)],
) -> FileResponse:
    """Serve the raw PDF file for download/viewing."""
    document = await doc_repo.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=document.file_path,
        filename=document.filename,
        media_type="application/pdf",
    )
