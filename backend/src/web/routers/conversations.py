from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import ConversationRepository
from db.session import get_session
from web.schemas.conversation import (
    ConversationDetail,
    ConversationListItem,
    ConversationUpdate,
    DocumentInfo,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


async def get_conversation_repo(
    session: AsyncSession = Depends(get_session),
) -> ConversationRepository:
    return ConversationRepository(session)


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@router.get("", response_model=list[ConversationListItem])
async def list_conversations_endpoint(
    repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
) -> list[ConversationListItem]:
    """List all conversations, ordered by most recently updated."""
    conversations = await repo.list()
    return [
        ConversationListItem(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            has_document=len(c.documents) > 0,
        )
        for c in conversations
    ]


@router.post("", response_model=ConversationDetail, status_code=201)
async def create_conversation_endpoint(
    repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
) -> ConversationDetail:
    """Create a new conversation."""
    from db.models import Conversation

    conversation = await repo.save(Conversation())
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        has_document=False,
        document=None,
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_endpoint(
    conversation_id: str,
    repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
) -> ConversationDetail:
    """Get a single conversation with its document info."""
    conversation = await repo.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    doc_info: DocumentInfo | None = None
    if conversation.documents:
        doc = conversation.documents[0]
        doc_info = DocumentInfo(
            id=doc.id,
            filename=doc.filename,
            page_count=doc.page_count,
            created_at=doc.created_at,
        )

    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        has_document=doc_info is not None,
        document=doc_info,
    )


@router.patch("/{conversation_id}", response_model=ConversationDetail)
async def update_conversation_endpoint(
    conversation_id: str,
    body: ConversationUpdate,
    repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
) -> ConversationDetail:
    """Update a conversation's title."""
    conversation = await repo.update_title(conversation_id, body.title)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    doc_info: DocumentInfo | None = None
    if conversation.documents:
        doc = conversation.documents[0]
        doc_info = DocumentInfo(
            id=doc.id,
            filename=doc.filename,
            page_count=doc.page_count,
            created_at=doc.created_at,
        )

    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        has_document=doc_info is not None,
        document=doc_info,
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation_endpoint(
    conversation_id: str,
    repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
) -> None:
    """Delete a conversation and all associated data."""
    deleted = await repo.delete(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
