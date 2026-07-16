from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient

# conftest.py provides: client, mock_conv_repo, conversation fixtures


# ---------------------------------------------------------------------------
# GET /api/conversations
# ---------------------------------------------------------------------------


async def test_list_conversations_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/conversations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "conv0000001test"
    assert data[0]["title"] == "Test Conversation"
    assert data[0]["has_document"] is False


async def test_list_conversations_empty(
    client: AsyncClient, mock_conv_repo: MagicMock
) -> None:
    mock_conv_repo.list = AsyncMock(return_value=[])
    response = await client.get("/api/conversations")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# POST /api/conversations
# ---------------------------------------------------------------------------


async def test_create_conversation_returns_201(client: AsyncClient) -> None:
    response = await client.post("/api/conversations")
    assert response.status_code == 201


async def test_create_conversation_response_shape(client: AsyncClient) -> None:
    response = await client.post("/api/conversations")
    data = response.json()
    assert "id" in data
    assert "title" in data
    assert data["has_document"] is False
    assert data["documents"] == []


async def test_create_conversation_calls_save(
    client: AsyncClient, mock_conv_repo: MagicMock
) -> None:
    await client.post("/api/conversations")
    mock_conv_repo.save.assert_called_once()


# ---------------------------------------------------------------------------
# GET /api/conversations/{id}
# ---------------------------------------------------------------------------


async def test_get_conversation_found(client: AsyncClient) -> None:
    response = await client.get("/api/conversations/conv0000001test")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "conv0000001test"
    assert data["documents"] == []


async def test_get_conversation_not_found(
    client: AsyncClient, mock_conv_repo: MagicMock
) -> None:
    mock_conv_repo.get = AsyncMock(return_value=None)
    response = await client.get("/api/conversations/does_not_exist")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# PATCH /api/conversations/{id}
# ---------------------------------------------------------------------------


async def test_update_title_returns_200(
    client: AsyncClient, mock_conv_repo: MagicMock, conversation: MagicMock
) -> None:
    conversation.title = "Updated Title"
    mock_conv_repo.update_title = AsyncMock(return_value=conversation)

    response = await client.patch(
        "/api/conversations/conv0000001test",
        json={"title": "Updated Title"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"


async def test_update_title_not_found(
    client: AsyncClient, mock_conv_repo: MagicMock
) -> None:
    mock_conv_repo.update_title = AsyncMock(return_value=None)
    response = await client.patch(
        "/api/conversations/nonexistent",
        json={"title": "Anything"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/conversations/{id}
# ---------------------------------------------------------------------------


async def test_delete_conversation_returns_204(client: AsyncClient) -> None:
    response = await client.delete("/api/conversations/conv0000001test")
    assert response.status_code == 204
    assert response.content == b""


async def test_delete_conversation_not_found(
    client: AsyncClient, mock_conv_repo: MagicMock
) -> None:
    mock_conv_repo.delete = AsyncMock(return_value=False)
    response = await client.delete("/api/conversations/nonexistent")
    assert response.status_code == 404
