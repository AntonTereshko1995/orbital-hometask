from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from services.embedding_store import load, save

_CHUNKS: list[dict[str, Any]] = [
    {"index": 0, "heading": "Rent", "content": "Rent is £5,000/month.", "embedding": [0.1, 0.2]},
    {"index": 1, "heading": None, "content": "Term is 10 years.", "embedding": [0.3, 0.4]},
]


async def test_save_creates_embeddings_subdir(tmp_path: Path) -> None:
    await save("doc1", "openai/text-embedding-3-small", _CHUNKS, str(tmp_path))
    embeddings_dir = tmp_path / "embeddings"
    assert embeddings_dir.is_dir()


async def test_save_returns_correct_path(tmp_path: Path) -> None:
    path = await save("doc1", "openai/text-embedding-3-small", _CHUNKS, str(tmp_path))
    expected = os.path.join(str(tmp_path), "embeddings", "doc1.json")
    assert path == expected


async def test_save_writes_valid_json(tmp_path: Path) -> None:
    path = await save("doc2", "openai/text-embedding-3-small", _CHUNKS, str(tmp_path))
    with open(path) as f:
        data = json.load(f)
    assert data["doc_id"] == "doc2"
    assert data["model"] == "openai/text-embedding-3-small"
    assert len(data["chunks"]) == 2


async def test_load_reads_saved_data(tmp_path: Path) -> None:
    path = await save("doc3", "openai/text-embedding-3-small", _CHUNKS, str(tmp_path))
    data = await load(path)
    assert data["doc_id"] == "doc3"
    assert len(data["chunks"]) == 2


async def test_save_load_roundtrip_preserves_all_fields(tmp_path: Path) -> None:
    path = await save("doc4", "openai/text-embedding-3-small", _CHUNKS, str(tmp_path))
    data = await load(path)

    chunk0 = data["chunks"][0]
    assert chunk0["index"] == 0
    assert chunk0["heading"] == "Rent"
    assert chunk0["content"] == "Rent is £5,000/month."
    assert chunk0["embedding"] == [0.1, 0.2]

    chunk1 = data["chunks"][1]
    assert chunk1["heading"] is None
    assert chunk1["embedding"] == [0.3, 0.4]
