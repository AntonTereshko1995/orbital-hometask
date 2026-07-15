from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import structlog

logger = structlog.get_logger()


async def save(
    doc_id: str,
    model: str,
    chunks: list[dict[str, Any]],
    upload_dir: str,
) -> str:
    """Write embedding index to disk. Returns the file path."""
    embeddings_dir = os.path.join(upload_dir, "embeddings")
    os.makedirs(embeddings_dir, exist_ok=True)
    path = os.path.join(embeddings_dir, f"{doc_id}.json")
    payload: dict[str, Any] = {"doc_id": doc_id, "model": model, "chunks": chunks}

    def _write() -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    await asyncio.to_thread(_write)
    logger.info("Embeddings saved", doc_id=doc_id, path=path, chunk_count=len(chunks))
    return path


async def load(path: str) -> dict[str, Any]:
    """Read embedding index from disk. Returns full payload dict."""

    def _read() -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]

    return await asyncio.to_thread(_read)
