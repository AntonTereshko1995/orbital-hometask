from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Conversation
from db.repositories import ConversationRepository
from db.session import get_session
from web.schemas.conversation import (
    ConversationDetail,
    ConversationListItem,
    ConversationUpdate,
    DocumentInfo,
    ShareInfo,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


async def get_conversation_repo(
    session: AsyncSession = Depends(get_session),
) -> ConversationRepository:
    return ConversationRepository(session)


def _make_doc_infos(conversation: Conversation) -> list[DocumentInfo]:
    return [
        DocumentInfo(
            id=doc.id,
            filename=doc.filename,
            file_size=doc.file_size,
            page_count=doc.page_count,
            created_at=doc.created_at,
        )
        for doc in conversation.documents
    ]


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@router.get("", response_model=list[ConversationListItem])
async def list_conversations_endpoint(
    repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
) -> list[ConversationListItem]:
    """List all conversations, ordered by pinned first then most recently updated."""
    conversations = await repo.list()
    return [
        ConversationListItem(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            has_document=len(c.documents) > 0,
            is_pinned=c.is_pinned,
            is_shared=c.is_shared,
            share_token=c.share_token,
        )
        for c in conversations
    ]


@router.post("", response_model=ConversationDetail, status_code=201)
async def create_conversation_endpoint(
    repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
) -> ConversationDetail:
    """Create a new conversation."""
    conversation = await repo.save(Conversation())
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        has_document=False,
        is_pinned=conversation.is_pinned,
        is_shared=conversation.is_shared,
        share_token=conversation.share_token,
        documents=[],
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_endpoint(
    conversation_id: str,
    repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
) -> ConversationDetail:
    """Get a single conversation with its documents info."""
    conversation = await repo.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    docs = _make_doc_infos(conversation)
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        has_document=len(docs) > 0,
        is_pinned=conversation.is_pinned,
        is_shared=conversation.is_shared,
        share_token=conversation.share_token,
        documents=docs,
    )


@router.patch("/{conversation_id}", response_model=ConversationDetail)
async def update_conversation_endpoint(
    conversation_id: str,
    body: ConversationUpdate,
    repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
) -> ConversationDetail:
    """Update a conversation's title and/or pin state."""
    conversation = await repo.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if body.title is not None:
        conversation = await repo.update_title(conversation_id, body.title)
    if body.is_pinned is not None:
        conversation = await repo.update_pin(conversation_id, body.is_pinned)

    assert conversation is not None

    docs = _make_doc_infos(conversation)
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        has_document=len(docs) > 0,
        is_pinned=conversation.is_pinned,
        is_shared=conversation.is_shared,
        share_token=conversation.share_token,
        documents=docs,
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


@router.post("/{conversation_id}/share", response_model=ShareInfo)
async def share_conversation_endpoint(
    conversation_id: str,
    repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
) -> ShareInfo:
    """Enable sharing for a conversation, generating a token if needed."""
    conversation = await repo.enable_share(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ShareInfo(is_shared=conversation.is_shared, share_token=conversation.share_token)


@router.delete("/{conversation_id}/share", status_code=204)
async def unshare_conversation_endpoint(
    conversation_id: str,
    repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
) -> None:
    """Disable sharing for a conversation."""
    disabled = await repo.disable_share(conversation_id)
    if not disabled:
        raise HTTPException(status_code=404, detail="Conversation not found")
