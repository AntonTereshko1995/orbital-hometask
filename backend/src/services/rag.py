from __future__ import annotations

import asyncio
import json
import math
import os
from typing import Any, cast

import litellm
import structlog

from config import settings
from services.document_index import ParsedSection

logger = structlog.get_logger()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return cosine similarity in [-1, 1]. Returns 0.0 if either vector is zero."""
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


async def generate_and_save_embeddings(
    doc_id: str,
    sections: list[ParsedSection],
    upload_dir: str,
) -> str | None:
    """Embed all section texts, persist to JSON, return the file path.

    Returns None when:
    - sections list is empty
    - embedding_model or embedding_api_key is not configured
    - the embedding API call fails (error is logged)
    Never raises — upload must succeed even without embeddings.
    """
    if not sections:
        return None
    if not settings.embedding_model or not settings.embedding_api_key:
        logger.warning("Embedding model/key not configured — skipping L3 indexing")
        return None

    try:
        texts = [s.content for s in sections]

        response = await litellm.aembedding(  # type: ignore[misc]
            model=settings.embedding_model,
            input=texts,
            api_key=settings.embedding_api_key,
        )

        chunks: list[dict[str, Any]] = []
        for i, section in enumerate(sections):
            embedding: list[float] = response.data[i]["embedding"]  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType,reportArgumentType]
            chunks.append(
                {
                    "index": section.index,
                    "heading": section.heading,
                    "content": section.content,
                    "embedding": embedding,
                }
            )

        embeddings_dir = os.path.join(upload_dir, "embeddings")
        os.makedirs(embeddings_dir, exist_ok=True)
        path = os.path.join(embeddings_dir, f"{doc_id}.json")

        payload: dict[str, Any] = {
            "doc_id": doc_id,
            "model": settings.embedding_model,
            "chunks": chunks,
        }

        def _write() -> None:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f)

        await asyncio.to_thread(_write)
        logger.info("Embeddings saved", doc_id=doc_id, path=path, chunk_count=len(chunks))
        return path
    except Exception as ex:
        logger.exception("Failed to generate or save embeddings", doc_id=doc_id, message=str(ex))
        return None


async def retrieve_top_k_chunks(
    query: str,
    embedding_path: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """Embed *query*, load the document embedding index, return the top-K chunks.

    Chunks are sorted by cosine similarity descending.
    Raises on embedding API failure (caller decides how to handle).
    """
    q_response = await litellm.aembedding(  # type: ignore[misc]
        model=settings.embedding_model,
        input=[query],
        api_key=settings.embedding_api_key,
    )
    query_vec: list[float] = cast(list[float], q_response.data[0]["embedding"])  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType,reportArgumentType]

    def _read() -> dict[str, Any]:
        with open(embedding_path, encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]

    data: dict[str, Any] = await asyncio.to_thread(_read)
    chunks: list[dict[str, Any]] = data.get("chunks", [])

    scored: list[tuple[float, dict[str, Any]]] = [
        (cosine_similarity(query_vec, chunk["embedding"]), chunk)
        for chunk in chunks
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    return [chunk for _, chunk in scored[:top_k]]
