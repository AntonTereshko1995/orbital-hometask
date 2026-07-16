from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient

# conftest.py provides: client, mock_conv_repo, mock_msg_repo fixtures

_TS = datetime(2024, 1, 1, 12, 0, 0)


# ---------------------------------------------------------------------------
# Helper — parse SSE body
# ---------------------------------------------------------------------------


def _parse_sse(raw: str) -> list[dict]:
    """Split raw SSE text into a list of parsed JSON event dicts."""
    events: list[dict] = []
    for block in raw.strip().split("\n\n"):
        for line in block.strip().splitlines():
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[len("data: "):]))
                except json.JSONDecodeError:
                    pass
    return events


def _saved_assistant_msg() -> MagicMock:
    m = MagicMock()
    m.id = "msg0000000001"
    m.conversation_id = "conv0000001test"
    m.role = "assistant"
    m.content = "Hello world"
    m.sources_cited = 0
    m.created_at = _TS
    return m


# ---------------------------------------------------------------------------
# GET /api/conversations/{id}/messages
# ---------------------------------------------------------------------------


async def test_list_messages_conversation_not_found(
    client: AsyncClient, mock_conv_repo: MagicMock
) -> None:
    mock_conv_repo.get = AsyncMock(return_value=None)
    response = await client.get("/api/conversations/unknown/messages")
    assert response.status_code == 404


async def test_list_messages_empty(client: AsyncClient) -> None:
    response = await client.get("/api/conversations/conv0000001test/messages")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_messages_returns_messages(
    client: AsyncClient, mock_msg_repo: MagicMock
) -> None:
    msg = MagicMock()
    msg.id = "msg0000000001"
    msg.conversation_id = "conv0000001test"
    msg.role = "user"
    msg.content = "What is the rent?"
    msg.sources_cited = 0
    msg.created_at = _TS

    mock_msg_repo.list_for_conversation = AsyncMock(return_value=[msg])

    response = await client.get("/api/conversations/conv0000001test/messages")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["role"] == "user"
    assert data[0]["content"] == "What is the rent?"


# ---------------------------------------------------------------------------
# POST /api/conversations/{id}/messages (SSE stream)
# ---------------------------------------------------------------------------


async def test_send_message_conversation_not_found(
    client: AsyncClient, mock_conv_repo: MagicMock
) -> None:
    mock_conv_repo.get = AsyncMock(return_value=None)
    response = await client.post(
        "/api/conversations/unknown/messages",
        json={"content": "Hello?"},
    )
    assert response.status_code == 404


async def test_send_message_streams_sse_events(client: AsyncClient) -> None:
    async def _fake_chat(*_args: object, **_kwargs: object) -> object:  # type: ignore[return]
        yield "Hello "
        yield "world"

    saved = _saved_assistant_msg()

    with patch("web.routers.messages.chat_with_document", new=_fake_chat):
        with patch(
            "web.routers.messages._save_assistant_message",
            new_callable=AsyncMock,
            return_value=saved,
        ):
            with patch(
                "web.routers.messages._maybe_generate_title",
                new_callable=AsyncMock,
            ):
                response = await client.post(
                    "/api/conversations/conv0000001test/messages",
                    json={"content": "What is the rent?"},
                )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = _parse_sse(response.text)
    types = [e["type"] for e in events]

    assert "content" in types
    assert "message" in types
    assert "done" in types

    content_chunks = [e["content"] for e in events if e["type"] == "content"]
    assert "Hello " in content_chunks
    assert "world" in content_chunks

    done = next(e for e in events if e["type"] == "done")
    assert "sources_cited" in done
    assert "message_id" in done


async def test_send_message_llm_error_yields_error_content(client: AsyncClient) -> None:
    async def _raising_chat(*_args: object, **_kwargs: object) -> object:  # type: ignore[return]
        raise RuntimeError("LLM connection failed")
        yield  # makes it an async generator

    saved = _saved_assistant_msg()
    saved.content = "I'm sorry, an error occurred while generating a response. Please try again."

    with patch("web.routers.messages.chat_with_document", new=_raising_chat):
        with patch(
            "web.routers.messages._save_assistant_message",
            new_callable=AsyncMock,
            return_value=saved,
        ):
            with patch(
                "web.routers.messages._maybe_generate_title",
                new_callable=AsyncMock,
            ):
                response = await client.post(
                    "/api/conversations/conv0000001test/messages",
                    json={"content": "What is the rent?"},
                )

    assert response.status_code == 200
    events = _parse_sse(response.text)
    content_events = [e for e in events if e["type"] == "content"]
    assert any("sorry" in e.get("content", "").lower() for e in content_events)


async def test_send_message_calls_generate_title_on_first_message(
    client: AsyncClient, mock_msg_repo: MagicMock
) -> None:
    # list_history returns [] → is_first_message = True → title should be generated
    mock_msg_repo.list_history = AsyncMock(return_value=[])

    async def _fake_chat(*_args: object, **_kwargs: object) -> object:  # type: ignore[return]
        yield "response"

    saved = _saved_assistant_msg()

    with patch("web.routers.messages.chat_with_document", new=_fake_chat):
        with patch(
            "web.routers.messages._save_assistant_message",
            new_callable=AsyncMock,
            return_value=saved,
        ):
            with patch(
                "web.routers.messages._maybe_generate_title",
                new_callable=AsyncMock,
            ) as mock_title:
                await client.post(
                    "/api/conversations/conv0000001test/messages",
                    json={"content": "First question"},
                )

    mock_title.assert_called_once()


async def test_send_message_skips_title_when_history_exists(
    client: AsyncClient, mock_msg_repo: MagicMock
) -> None:
    # Simulate a prior user message in history
    prior_user_msg = MagicMock()
    prior_user_msg.role = "user"
    prior_user_msg.content = "Earlier question"
    mock_msg_repo.list_history = AsyncMock(return_value=[prior_user_msg])

    async def _fake_chat(*_args: object, **_kwargs: object) -> object:  # type: ignore[return]
        yield "response"

    saved = _saved_assistant_msg()

    with patch("web.routers.messages.chat_with_document", new=_fake_chat):
        with patch(
            "web.routers.messages._save_assistant_message",
            new_callable=AsyncMock,
            return_value=saved,
        ):
            with patch(
                "web.routers.messages._maybe_generate_title",
                new_callable=AsyncMock,
            ) as mock_title:
                await client.post(
                    "/api/conversations/conv0000001test/messages",
                    json={"content": "Follow-up question"},
                )

    mock_title.assert_not_called()
