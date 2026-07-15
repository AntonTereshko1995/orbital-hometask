from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai.embeddings import cosine_similarity, generate_and_save_embeddings, retrieve_top_k_chunks
from services.document_index import ParsedSection

# ---------------------------------------------------------------------------
# cosine_similarity — pure math, no mocking needed
# ---------------------------------------------------------------------------


def test_cosine_similarity_identical_vectors() -> None:
    v = [1.0, 0.0, 0.0]
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_opposite_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_zero_vector_a() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_cosine_similarity_zero_vector_b() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 0.0]) == 0.0


def test_cosine_similarity_both_zero() -> None:
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


def test_cosine_similarity_arbitrary() -> None:
    a = [3.0, 4.0]
    b = [4.0, 3.0]
    # dot=24, norm_a=5, norm_b=5 → 24/25 = 0.96
    assert cosine_similarity(a, b) == pytest.approx(0.96)


# ---------------------------------------------------------------------------
# generate_and_save_embeddings
# ---------------------------------------------------------------------------

FAKE_DIM = 1536
FAKE_EMBEDDING = [0.1] * FAKE_DIM


def _make_mock_response(count: int) -> MagicMock:
    mock_response = MagicMock()
    # Use plain dicts so that response.data[i]["embedding"] (subscript) returns the
    # actual embedding list, matching litellm's real response structure.
    mock_response.data = [{"embedding": FAKE_EMBEDDING} for _ in range(count)]
    return mock_response


@pytest.mark.asyncio
async def test_generate_saves_json_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sections = [
        ParsedSection(index=0, heading="Section 1", content="Rent is £5000 per month.", token_count=8),
        ParsedSection(index=1, heading=None, content="Term is ten (10) years.", token_count=6),
    ]
    monkeypatch.setattr("ai.embeddings.settings.embedding_model", "openai/text-embedding-3-small")
    monkeypatch.setattr("ai.embeddings.settings.embedding_api_key", "sk-fake")

    with patch("litellm.aembedding", new_callable=AsyncMock, return_value=_make_mock_response(2)):
        path = await generate_and_save_embeddings("doc123", sections, str(tmp_path))

    assert path is not None
    assert os.path.exists(path)

    with open(path) as f:
        data = json.load(f)

    assert data["doc_id"] == "doc123"
    assert data["model"] == "openai/text-embedding-3-small"
    assert len(data["chunks"]) == 2

    chunk0 = data["chunks"][0]
    assert chunk0["index"] == 0
    assert chunk0["heading"] == "Section 1"
    assert chunk0["content"] == "Rent is £5000 per month."
    assert len(chunk0["embedding"]) == FAKE_DIM

    chunk1 = data["chunks"][1]
    assert chunk1["heading"] is None


@pytest.mark.asyncio
async def test_generate_returns_none_when_model_unconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai.embeddings.settings.embedding_model", "")
    sections = [ParsedSection(index=0, heading=None, content="x", token_count=1)]
    result = await generate_and_save_embeddings("doc1", sections, str(tmp_path))
    assert result is None


@pytest.mark.asyncio
async def test_generate_returns_none_when_api_key_unconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai.embeddings.settings.embedding_model", "openai/text-embedding-3-small")
    monkeypatch.setattr("ai.embeddings.settings.embedding_api_key", "")
    sections = [ParsedSection(index=0, heading=None, content="x", token_count=1)]
    result = await generate_and_save_embeddings("doc1", sections, str(tmp_path))
    assert result is None


@pytest.mark.asyncio
async def test_generate_returns_none_for_empty_sections(tmp_path: Path) -> None:
    result = await generate_and_save_embeddings("doc1", [], str(tmp_path))
    assert result is None


@pytest.mark.asyncio
async def test_generate_returns_none_on_api_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai.embeddings.settings.embedding_model", "openai/text-embedding-3-small")
    monkeypatch.setattr("ai.embeddings.settings.embedding_api_key", "sk-fake")
    sections = [ParsedSection(index=0, heading=None, content="x", token_count=1)]

    with patch("litellm.aembedding", new_callable=AsyncMock, side_effect=RuntimeError("API error")):
        result = await generate_and_save_embeddings("doc1", sections, str(tmp_path))

    assert result is None


@pytest.mark.asyncio
async def test_generate_creates_embeddings_subdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai.embeddings.settings.embedding_model", "openai/text-embedding-3-small")
    monkeypatch.setattr("ai.embeddings.settings.embedding_api_key", "sk-fake")
    sections = [ParsedSection(index=0, heading="H", content="content", token_count=1)]

    with patch("litellm.aembedding", new_callable=AsyncMock, return_value=_make_mock_response(1)):
        path = await generate_and_save_embeddings("docabc", sections, str(tmp_path))

    assert path is not None
    expected_dir = os.path.join(str(tmp_path), "embeddings")
    assert os.path.isdir(expected_dir)
    assert path == os.path.join(expected_dir, "docabc.json")


# ---------------------------------------------------------------------------
# retrieve_top_k_chunks
# ---------------------------------------------------------------------------

_CHUNKS_DATA = [
    {
        "index": 0,
        "heading": "Rent",
        "content": "Rent clause content.",
        "embedding": [1.0, 0.0, 0.0],
    },
    {
        "index": 1,
        "heading": "Term",
        "content": "Term clause content.",
        "embedding": [0.0, 1.0, 0.0],
    },
    {
        "index": 2,
        "heading": "Obligations",
        "content": "Obligations content.",
        "embedding": [0.0, 0.0, 1.0],
    },
]


def _write_embedding_file(tmp_path: Path, chunks: list[dict]) -> Path:
    data = {"doc_id": "d1", "model": "test", "chunks": chunks}
    path = tmp_path / "d1.json"
    path.write_text(json.dumps(data))
    return path


@pytest.mark.asyncio
async def test_retrieve_returns_top_k_most_similar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai.embeddings.settings.embedding_model", "openai/text-embedding-3-small")
    monkeypatch.setattr("ai.embeddings.settings.embedding_api_key", "sk-fake")

    emb_file = _write_embedding_file(tmp_path, _CHUNKS_DATA)

    # Query vector aligned with "Rent" chunk
    mock_response = MagicMock()
    mock_response.data = [{"embedding": [1.0, 0.0, 0.0]}]

    with patch("litellm.aembedding", new_callable=AsyncMock, return_value=mock_response):
        results = await retrieve_top_k_chunks(
            query="rent amount",
            embedding_path=str(emb_file),
            top_k=1,
        )

    assert len(results) == 1
    assert results[0]["heading"] == "Rent"


@pytest.mark.asyncio
async def test_retrieve_respects_top_k_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai.embeddings.settings.embedding_model", "openai/text-embedding-3-small")
    monkeypatch.setattr("ai.embeddings.settings.embedding_api_key", "sk-fake")

    emb_file = _write_embedding_file(tmp_path, _CHUNKS_DATA)

    mock_response = MagicMock()
    mock_response.data = [{"embedding": [1.0, 0.0, 0.0]}]

    with patch("litellm.aembedding", new_callable=AsyncMock, return_value=mock_response):
        results = await retrieve_top_k_chunks(
            query="rent",
            embedding_path=str(emb_file),
            top_k=2,
        )

    assert len(results) == 2


@pytest.mark.asyncio
async def test_retrieve_returns_sorted_by_similarity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai.embeddings.settings.embedding_model", "openai/text-embedding-3-small")
    monkeypatch.setattr("ai.embeddings.settings.embedding_api_key", "sk-fake")

    emb_file = _write_embedding_file(tmp_path, _CHUNKS_DATA)

    # Query between Rent and Term vectors — Rent should score higher
    mock_response = MagicMock()
    mock_response.data = [{"embedding": [0.9, 0.1, 0.0]}]

    with patch("litellm.aembedding", new_callable=AsyncMock, return_value=mock_response):
        results = await retrieve_top_k_chunks(
            query="rent",
            embedding_path=str(emb_file),
            top_k=3,
        )

    assert results[0]["heading"] == "Rent"
    assert results[1]["heading"] == "Term"


@pytest.mark.asyncio
async def test_retrieve_top_k_larger_than_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai.embeddings.settings.embedding_model", "openai/text-embedding-3-small")
    monkeypatch.setattr("ai.embeddings.settings.embedding_api_key", "sk-fake")

    emb_file = _write_embedding_file(tmp_path, _CHUNKS_DATA)

    mock_response = MagicMock()
    mock_response.data = [{"embedding": [1.0, 0.0, 0.0]}]

    with patch("litellm.aembedding", new_callable=AsyncMock, return_value=mock_response):
        results = await retrieve_top_k_chunks(
            query="anything",
            embedding_path=str(emb_file),
            top_k=100,
        )

    # Should return all 3 chunks, not crash
    assert len(results) == 3
