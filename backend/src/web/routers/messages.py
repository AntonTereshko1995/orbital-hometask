from __future__ import annotations

import json
from collections.abc import AsyncIterator

import structlog
from ai.analysis import count_sources_cited
from ai.pipeline import chat_with_document, generate_title
from db.models import Message
from db.session import async_session as session_factory
from db.session import get_session
from fastapi import APIRouter, Depends, HTTPException
from services.conversation import get_conversation, update_conversation
from services.document import get_document_for_conversation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse
from web.schemas.message import MessageCreate, MessageOut

logger = structlog.get_logger()

router = APIRouter(tags=["messages"])


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


async def _save_assistant_message(
    conversation_id: str, full_response: str, sources: int
) -> Message:
    """Persist the streamed assistant reply to the database."""
    async with session_factory() as session:
        msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=full_response,
            sources_cited=sources,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg


async def _maybe_generate_title(conversation_id: str, user_content: str) -> None:
    """Generate and persist a conversation title on the first message."""
    async with session_factory() as session:
        try:
            title = await generate_title(user_content)
            await update_conversation(session, conversation_id, title)
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
    session: AsyncSession = Depends(get_session),
) -> list[MessageOut]:
    """List all messages in a conversation, ordered by creation time."""
    conversation = await get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    result = await session.execute(stmt)
    messages = list(result.scalars().all())

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
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Send a user message and stream back the AI response via SSE."""
    conversation = await get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        content=body.content,
    )
    session.add(user_message)
    await session.commit()
    await session.refresh(user_message)

    logger.info("User message saved", conversation_id=conversation_id, message_id=user_message.id)

    document = await get_document_for_conversation(session, conversation_id)
    document_text: str | None = document.extracted_text if document else None

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .where(Message.id != user_message.id)
        .order_by(Message.created_at.asc())
    )
    result = await session.execute(stmt)
    history_messages = list(result.scalars().all())

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
                document_text=document_text,
                conversation_history=conversation_history,
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
