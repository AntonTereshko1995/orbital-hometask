from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient

from tests.conftest import _conv, _msg


# ---------------------------------------------------------------------------
# GET /api/shared/{token}
# ---------------------------------------------------------------------------


async def test_get_shared_conversation_found(
    client: AsyncClient, mock_conv_repo: MagicMock, mock_msg_repo: MagicMock
) -> None:
    conv = _conv()
    conv.is_shared = True
    conv.share_token = "abc123sharetoken"
    mock_conv_repo.get_by_share_token = AsyncMock(return_value=conv)
    mock_msg_repo.list_for_conversation = AsyncMock(return_value=[_msg()])

    response = await client.get("/api/shared/abc123sharetoken")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Conversation"
    assert "documents" in data
    assert "messages" in data
    assert len(data["messages"]) == 1
    assert data["messages"][0]["role"] == "assistant"
    assert data["messages"][0]["content"] == "Test response"
    assert data["messages"][0]["sources_cited"] == 0


async def test_get_shared_conversation_no_messages(
    client: AsyncClient, mock_conv_repo: MagicMock, mock_msg_repo: MagicMock
) -> None:
    conv = _conv()
    conv.is_shared = True
    conv.share_token = "emptytokenxyz"
    mock_conv_repo.get_by_share_token = AsyncMock(return_value=conv)
    mock_msg_repo.list_for_conversation = AsyncMock(return_value=[])

    response = await client.get("/api/shared/emptytokenxyz")
    assert response.status_code == 200
    data = response.json()
    assert data["messages"] == []
    assert data["documents"] == []


async def test_get_shared_conversation_not_found(
    client: AsyncClient, mock_conv_repo: MagicMock
) -> None:
    mock_conv_repo.get_by_share_token = AsyncMock(return_value=None)
    response = await client.get("/api/shared/badtoken")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
