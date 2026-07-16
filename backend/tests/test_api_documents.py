from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient

from tests.conftest import _doc

# conftest.py provides: client, mock_conv_repo, mock_doc_repo fixtures

_FAKE_PDF = b"%PDF-1.4 fake document content"


# ---------------------------------------------------------------------------
# POST /api/conversations/{id}/documents
# ---------------------------------------------------------------------------


async def test_upload_document_conversation_not_found(
    client: AsyncClient, mock_conv_repo: MagicMock
) -> None:
    mock_conv_repo.get = AsyncMock(return_value=None)
    response = await client.post(
        "/api/conversations/nonexistent/documents",
        files={"file": ("test.pdf", _FAKE_PDF, "application/pdf")},
    )
    assert response.status_code == 404


async def test_upload_document_success(
    client: AsyncClient, mock_conv_repo: MagicMock
) -> None:
    document = _doc()

    with patch(
        "web.routers.documents.upload_document",
        new_callable=AsyncMock,
        return_value=document,
    ):
        response = await client.post(
            "/api/conversations/conv0000001test/documents",
            files={"file": ("test.pdf", _FAKE_PDF, "application/pdf")},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "doc0000000001"
    assert data["filename"] == "test.pdf"
    assert data["conversation_id"] == "conv0000001test"
    assert data["page_count"] == 5


async def test_upload_document_invalid_file_returns_400(
    client: AsyncClient, mock_conv_repo: MagicMock
) -> None:
    with patch(
        "web.routers.documents.upload_document",
        new_callable=AsyncMock,
        side_effect=ValueError("Only PDF files are supported."),
    ):
        response = await client.post(
            "/api/conversations/conv0000001test/documents",
            files={"file": ("doc.txt", b"not a pdf", "text/plain")},
        )

    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/documents/{id}/content
# ---------------------------------------------------------------------------


async def test_serve_document_not_found(
    client: AsyncClient, mock_doc_repo: MagicMock
) -> None:
    mock_doc_repo.get = AsyncMock(return_value=None)
    response = await client.get("/api/documents/nonexistent/content")
    assert response.status_code == 404
    assert "Document not found" in response.json()["detail"]


async def test_serve_document_file_missing_on_disk(
    client: AsyncClient, mock_doc_repo: MagicMock
) -> None:
    mock_doc = _doc(file_path="/nonexistent/path/file.pdf")
    mock_doc_repo.get = AsyncMock(return_value=mock_doc)

    response = await client.get("/api/documents/doc0000000001/content")
    assert response.status_code == 404
    assert "File not found" in response.json()["detail"]


async def test_serve_document_returns_pdf(
    client: AsyncClient, mock_doc_repo: MagicMock, tmp_path: Path
) -> None:
    pdf_file = tmp_path / "real.pdf"
    pdf_file.write_bytes(_FAKE_PDF)

    mock_doc = _doc(file_path=str(pdf_file))
    mock_doc_repo.get = AsyncMock(return_value=mock_doc)

    response = await client.get("/api/documents/doc0000000001/content")
    assert response.status_code == 200
    assert "application/pdf" in response.headers["content-type"]
    assert response.content == _FAKE_PDF
