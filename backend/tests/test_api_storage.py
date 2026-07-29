from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient

from tests.conftest import _doc


# ---------------------------------------------------------------------------
# GET /api/storage
# ---------------------------------------------------------------------------


async def test_list_library_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/storage")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_list_library_empty(
    client: AsyncClient, mock_doc_repo: MagicMock
) -> None:
    mock_doc_repo.list = AsyncMock(return_value=[])
    response = await client.get("/api/storage")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_library_returns_documents(
    client: AsyncClient, mock_doc_repo: MagicMock
) -> None:
    doc = _doc()
    mock_doc_repo.list = AsyncMock(return_value=[doc])

    response = await client.get("/api/storage")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "doc0000000001"
    assert data[0]["filename"] == "test.pdf"
    assert data[0]["file_size"] == 1000
    assert data[0]["page_count"] == 5
    assert "conversation_id" not in data[0]
