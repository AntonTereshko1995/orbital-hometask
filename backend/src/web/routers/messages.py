from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from ai.analysis import count_sources_cited
from ai.pipeline import chat_with_document, generate_title
from ai.types import DocContext, SectionData
from db.models import Message
from db.repositories import (
    ConversationRepository,
    DocumentRepository,
    DocumentSectionRepository,
    MessageRepository,
)
from db.session import async_session as session_factory
from db.session import get_session
from web.schemas.message import MessageCreate, MessageOut

logger = structlog.get_logger()

router = APIRouter(tags=["messages"])


async def get_conversation_repo(
    session: AsyncSession = Depends(get_session),
) -> ConversationRepository:
    return ConversationRepository(session)


async def get_document_repo(
    session: AsyncSession = Depends(get_session),
) -> DocumentRepository:
    return DocumentRepository(session)


async def get_message_repo(
    session: AsyncSession = Depends(get_session),
) -> MessageRepository:
    return MessageRepository(session)


async def get_section_repo(
    session: AsyncSession = Depends(get_session),
) -> DocumentSectionRepository:
    return DocumentSectionRepository(session)


# --------------------------------------------------------------------------- #
# Helpers (open their own sessions — called inside the SSE generator after
# the request-scoped session has been closed)
# --------------------------------------------------------------------------- #


async def _save_assistant_message(
    conversation_id: str, full_response: str, sources: int
) -> Message:
    """Persist the streamed assistant reply to the database."""
    async with session_factory() as session:
        repo = MessageRepository(session)
        msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=full_response,
            sources_cited=sources,
        )
        return await repo.save(msg)


async def _maybe_generate_title(conversation_id: str, user_content: str) -> None:
    """Generate and persist a conversation title on the first message."""
    async with session_factory() as session:
        repo = ConversationRepository(session)
        try:
            title = await generate_title(user_content)
            await repo.update_title(conversation_id, title)
            logger.info("Auto-generated title", conversation_id=conversation_id, title=title)
        except Exception:
            logger.exception("Failed to generate title", conversation_id=conversation_id)


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@router.get(
    "/api/conversations/{conversation_id}/messages",
    response_model=list[MessageOut],
)
async def list_messages(
    conversation_id: str,
    conv_repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
    msg_repo: Annotated[MessageRepository, Depends(get_message_repo)],
) -> list[MessageOut]:
    """List all messages in a conversation, ordered by creation time."""
    conversation = await conv_repo.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await msg_repo.list_for_conversation(conversation_id)

    return [
        MessageOut(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            sources_cited=m.sources_cited,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.post("/api/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: MessageCreate,
    conv_repo: Annotated[ConversationRepository, Depends(get_conversation_repo)],
    msg_repo: Annotated[MessageRepository, Depends(get_message_repo)],
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repo)],
    section_repo: Annotated[DocumentSectionRepository, Depends(get_section_repo)],
) -> StreamingResponse:
    """Send a user message and stream back the AI response via SSE."""
    conversation = await conv_repo.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        content=body.content,
    )
    await msg_repo.save(user_message)

    logger.info("User message saved", conversation_id=conversation_id, message_id=user_message.id)

    all_docs = await doc_repo.list_for_conversation(conversation_id)
    doc_contexts: list[DocContext] = [
        {
            "id": doc.id,
            "filename": doc.filename,
            "text": doc.extracted_text or "",
            "embedding_path": doc.embedding_path,
        }
        for doc in all_docs
    ]

    # Load sections before the StreamingResponse is created so the request-scoped
    # session (section_repo._session) is still open when we read from it.
    sections_by_doc: dict[str, list[SectionData]] = {}
    for doc in all_docs:
        raw = await section_repo.list_for_document(doc.id)
        sections_by_doc[doc.id] = [
            SectionData(
                id=s.id,
                doc_id=s.document_id,
                index=s.section_index,
                heading=s.heading,
                content=s.content,
                token_count=s.token_count,
            )
            for s in raw
        ]

    history_messages = await msg_repo.list_history(conversation_id, user_message.id)
    conversation_history: list[dict[str, str]] = [
        {"role": m.role, "content": m.content} for m in history_messages
    ]
    is_first_message = sum(1 for m in history_messages if m.role == "user") == 0

    async def event_stream() -> AsyncIterator[str]:
        """Generate SSE events for the streamed LLM response."""
        full_response = ""

        try:
            async for chunk in chat_with_document(
                user_message=body.content,
                documents=doc_contexts,
                conversation_history=conversation_history,
                sections_by_doc=sections_by_doc,
            ):
                full_response += chunk
                event_data = json.dumps({"type": "content", "content": chunk})
                yield f"data: {event_data}\n\n"

        except Exception:
            logger.exception("Error during LLM streaming", conversation_id=conversation_id)
            error_msg = "I'm sorry, an error occurred while generating a response. Please try again."
            full_response = error_msg
            event_data = json.dumps({"type": "content", "content": error_msg})
            yield f"data: {event_data}\n\n"

        sources = count_sources_cited(full_response)
        assistant_message = await _save_assistant_message(conversation_id, full_response, sources)

        if is_first_message:
            await _maybe_generate_title(conversation_id, body.content)

        message_data = json.dumps({
            "type": "message",
            "message": {
                "id": assistant_message.id,
                "conversation_id": assistant_message.conversation_id,
                "role": assistant_message.role,
                "content": assistant_message.content,
                "sources_cited": assistant_message.sources_cited,
                "created_at": assistant_message.created_at.isoformat(),
            },
        })
        yield f"data: {message_data}\n\n"

        done_data = json.dumps({
            "type": "done",
            "sources_cited": sources,
            "message_id": assistant_message.id,
        })
        yield f"data: {done_data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
