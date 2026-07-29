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
from web.schemas.document import AttachFromLibraryRequest, DocumentOut

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

    If the same file (filename + size) is already in the library it will be
    reused and reused_from_library will be True in the response.
    """
    conversation = await conv_repo.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    try:
        document, reused = await upload_document(session, conversation_id, file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    logger.info(
        "Document added to conversation",
        conversation_id=conversation_id,
        document_id=document.id,
        filename=document.filename,
        reused_from_library=reused,
    )

    return DocumentOut(
        id=document.id,
        filename=document.filename,
        file_size=document.file_size,
        page_count=document.page_count,
        created_at=document.created_at,
        reused_from_library=reused,
    )


@router.post(
    "/api/conversations/{conversation_id}/documents/from-library",
    response_model=DocumentOut,
    status_code=201,
)
async def attach_from_library_endpoint(
    conversation_id: str,
    body: AttachFromLibraryRequest,
    conv_repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repo)],
) -> DocumentOut:
    """Attach an existing library document to a conversation without re-uploading."""
    conversation = await conv_repo.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    document = await doc_repo.get(body.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found in library")

    await doc_repo.attach_to_conversation(document.id, conversation_id)

    logger.info(
        "Library document attached to conversation",
        conversation_id=conversation_id,
        document_id=document.id,
    )

    return DocumentOut(
        id=document.id,
        filename=document.filename,
        file_size=document.file_size,
        page_count=document.page_count,
        created_at=document.created_at,
        reused_from_library=True,
    )


@router.delete("/api/documents/{document_id}", status_code=204)
async def delete_document_endpoint(
    document_id: str,
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repo)],
) -> None:
    """Delete a document from the library.

    Cascades to conversation_documents (conversations lose the document) and
    document_sections. The file on disk is NOT deleted.
    """
    deleted = await doc_repo.delete(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")


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
