from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories import ConversationRepository, MessageRepository
from db.session import get_session
from web.schemas.conversation import DocumentInfo
from web.schemas.sharing import SharedConversationOut, SharedMessageOut

logger = structlog.get_logger()

router = APIRouter(prefix="/api/shared", tags=["sharing"])


async def get_conversation_repo(
    session: AsyncSession = Depends(get_session),
) -> ConversationRepository:
    return ConversationRepository(session)


async def get_message_repo(
    session: AsyncSession = Depends(get_session),
) -> MessageRepository:
    return MessageRepository(session)


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@router.get("/{token}", response_model=SharedConversationOut)
async def get_shared_conversation(
    token: str,
    conv_repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
    msg_repo: Annotated[MessageRepository, Depends(get_message_repo)],
) -> SharedConversationOut:
    """Return a read-only view of a shared conversation by its share token."""
    conversation = await conv_repo.get_by_share_token(token)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found or sharing disabled")

    messages = await msg_repo.list_for_conversation(conversation.id)

    return SharedConversationOut(
        title=conversation.title,
        created_at=conversation.created_at,
        documents=[
            DocumentInfo(
                id=d.id,
                filename=d.filename,
                file_size=d.file_size,
                page_count=d.page_count,
                created_at=d.created_at,
            )
            for d in conversation.documents
        ],
        messages=[
            SharedMessageOut(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                sources_cited=m.sources_cited,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )
