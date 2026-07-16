from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai.pipeline import chat_with_document, estimate_tokens, generate_title
from ai.types import DocContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc(text: str = "lease content", embedding_path: str | None = None) -> DocContext:
    return {
        "id": "d1",
        "filename": "lease.pdf",
        "text": text,
        "embedding_path": embedding_path,
    }


def _mock_litellm(token_count: int = 0) -> MagicMock:
    m = MagicMock()
    m.token_counter.return_value = token_count
    return m


async def _fake_full(*_args: object, **_kwargs: object) -> object:  # type: ignore[return]
    yield "full_context_chunk"


async def _fake_agentic(*_args: object, **_kwargs: object) -> object:  # type: ignore[return]
    yield "agentic_chunk"


async def _fake_rag(*_args: object, **_kwargs: object) -> object:  # type: ignore[return]
    yield "rag_chunk"


async def _collect(gen: object) -> list[str]:
    """Consume an async generator and return its chunks as a list."""
    chunks: list[str] = []
    async for chunk in gen:  # type: ignore[union-attr]
        chunks.append(chunk)
    return chunks


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------


def test_estimate_tokens_no_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_ll = _mock_litellm()
    monkeypatch.setattr("ai.pipeline.litellm", mock_ll)
    assert estimate_tokens([]) == 0
    mock_ll.token_counter.assert_not_called()


def test_estimate_tokens_single_doc(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_ll = _mock_litellm(token_count=150)
    monkeypatch.setattr("ai.pipeline.litellm", mock_ll)
    result = estimate_tokens([_doc("some text")])
    assert result == 150
    mock_ll.token_counter.assert_called_once()


def test_estimate_tokens_empty_text_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_ll = _mock_litellm(token_count=999)
    monkeypatch.setattr("ai.pipeline.litellm", mock_ll)
    result = estimate_tokens([_doc(text="")])
    assert result == 0
    mock_ll.token_counter.assert_not_called()


def test_estimate_tokens_multiple_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_ll = MagicMock()
    mock_ll.token_counter.side_effect = [100, 200]
    monkeypatch.setattr("ai.pipeline.litellm", mock_ll)
    docs = [_doc("text1"), _doc("text2")]
    assert estimate_tokens(docs) == 300
    assert mock_ll.token_counter.call_count == 2


# ---------------------------------------------------------------------------
# chat_with_document — routing strategy
# ---------------------------------------------------------------------------


async def test_routes_full_context_for_small_doc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ai.pipeline.litellm", _mock_litellm(token_count=100))

    with patch("ai.pipeline._stream_full_context", new=_fake_full):
        chunks = await _collect(chat_with_document("q", [_doc()], []))

    assert chunks == ["full_context_chunk"]


async def test_routes_full_context_for_no_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ai.pipeline.litellm", _mock_litellm(token_count=0))

    with patch("ai.pipeline._stream_full_context", new=_fake_full):
        chunks = await _collect(chat_with_document("q", [], []))

    assert chunks == ["full_context_chunk"]


async def test_routes_agentic_for_medium_doc(monkeypatch: pytest.MonkeyPatch) -> None:
    # 5 000 tokens: above agentic_threshold (2 000) and below rag_threshold (10 000)
    monkeypatch.setattr("ai.pipeline.litellm", _mock_litellm(token_count=5_000))

    with patch("ai.pipeline._stream_agentic_search", new=_fake_agentic):
        chunks = await _collect(
            chat_with_document(
                "q",
                [_doc()],  # embedding_path=None → no semantic RAG
                [],
                sections_by_doc={"d1": []},
            )
        )

    assert chunks == ["agentic_chunk"]


async def test_routes_semantic_rag_for_large_doc_with_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 15 000 tokens: above rag_threshold; doc has embedding_path set
    monkeypatch.setattr("ai.pipeline.litellm", _mock_litellm(token_count=15_000))
    doc_with_emb = _doc(embedding_path="/uploads/embeddings/d1.json")

    with patch("ai.pipeline._stream_semantic_rag", new=_fake_rag):
        chunks = await _collect(
            chat_with_document("q", [doc_with_emb], [], sections_by_doc={"d1": []})
        )

    assert chunks == ["rag_chunk"]


async def test_routes_full_context_for_large_doc_without_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 15 000 tokens but no embedding_path → semantic RAG condition fails
    # Also 15 000 >= rag_threshold so agentic condition (< rag_threshold) fails too
    monkeypatch.setattr("ai.pipeline.litellm", _mock_litellm(token_count=15_000))

    with patch("ai.pipeline._stream_full_context", new=_fake_full):
        chunks = await _collect(
            chat_with_document("q", [_doc()], [], sections_by_doc={"d1": []})
        )

    assert chunks == ["full_context_chunk"]


async def test_routes_full_context_when_sections_by_doc_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Medium tokens but sections_by_doc=None → agentic search cannot run
    monkeypatch.setattr("ai.pipeline.litellm", _mock_litellm(token_count=5_000))

    with patch("ai.pipeline._stream_full_context", new=_fake_full):
        chunks = await _collect(
            chat_with_document("q", [_doc()], [], sections_by_doc=None)
        )

    assert chunks == ["full_context_chunk"]


# ---------------------------------------------------------------------------
# generate_title
# ---------------------------------------------------------------------------


async def test_generate_title_strips_quotes(monkeypatch: pytest.MonkeyPatch) -> None:
    choice = MagicMock()
    choice.message.content = '"Rent Payment Terms"'
    mock_resp = MagicMock()
    mock_resp.choices = [choice]

    mock_ll = MagicMock()
    mock_ll.acompletion = AsyncMock(return_value=mock_resp)
    monkeypatch.setattr("ai.pipeline.litellm", mock_ll)

    title = await generate_title("What is the monthly rent?")
    assert title == "Rent Payment Terms"


async def test_generate_title_truncates_long_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_title = "A" * 120
    choice = MagicMock()
    choice.message.content = long_title
    mock_resp = MagicMock()
    mock_resp.choices = [choice]

    mock_ll = MagicMock()
    mock_ll.acompletion = AsyncMock(return_value=mock_resp)
    monkeypatch.setattr("ai.pipeline.litellm", mock_ll)

    title = await generate_title("Some very verbose first message.")
    assert len(title) == 100
    assert title.endswith("...")


async def test_generate_title_empty_content(monkeypatch: pytest.MonkeyPatch) -> None:
    choice = MagicMock()
    choice.message.content = None
    mock_resp = MagicMock()
    mock_resp.choices = [choice]

    mock_ll = MagicMock()
    mock_ll.acompletion = AsyncMock(return_value=mock_resp)
    monkeypatch.setattr("ai.pipeline.litellm", mock_ll)

    title = await generate_title("Hello")
    assert title == ""
