from __future__ import annotations

import json
from typing import Any

from ai.types import DocContext, SectionData

__all__ = ["DocContext", "SectionData", "dispatch_tool", "TOOL_SCHEMAS"]

# ---------------------------------------------------------------------------
# Tool implementations — all synchronous, operate on in-memory data only.
# ---------------------------------------------------------------------------


def get_document_metadata(
    doc_id: str,
    doc_map: dict[str, DocContext],
    sections: list[SectionData],
) -> dict[str, object]:
    if doc_id not in doc_map:
        return {"error": f"Document {doc_id!r} not found"}
    doc = doc_map[doc_id]
    total_tokens = sum(s["token_count"] for s in sections)
    return {
        "id": doc_id,
        "filename": doc["filename"],
        "total_tokens": total_tokens,
        "section_count": len(sections),
    }


def get_document_outline(
    sections: list[SectionData],
) -> list[dict[str, object]]:
    return [
        {
            "index": s["index"],
            "heading": s["heading"] if s["heading"] is not None else f"Block {s['index']}",
            "tokens": s["token_count"],
        }
        for s in sections
    ]


def search_document(
    query: str,
    sections: list[SectionData],
) -> list[dict[str, object]]:
    query_lower = query.lower()
    results: list[dict[str, object]] = []
    for s in sections:
        content_lower = s["content"].lower()
        idx = content_lower.find(query_lower)
        if idx == -1:
            continue
        start = max(0, idx - 100)
        end = min(len(s["content"]), idx + len(query) + 100)
        snippet = s["content"][start:end]
        results.append(
            {
                "section_index": s["index"],
                "heading": s["heading"],
                "snippet": snippet,
            }
        )
        if len(results) >= 10:
            break
    return results


def read_document_section(
    section_index: int,
    sections: list[SectionData],
) -> str:
    for s in sections:
        if s["index"] == section_index:
            prefix = f"## {s['heading']}\n" if s["heading"] else ""
            return prefix + s["content"]
    return f"Section {section_index} not found."


def read_document_chunk(
    start_index: int,
    end_index: int,
    sections: list[SectionData],
) -> str:
    chunk = [s for s in sections if start_index <= s["index"] <= end_index]
    if not chunk:
        return f"No sections found between index {start_index} and {end_index}."
    parts: list[str] = []
    for s in chunk:
        prefix = f"## {s['heading']}\n" if s["heading"] else ""
        parts.append(prefix + s["content"])
    return "\n\n".join(parts)


def read_document_head(
    n: int,
    sections: list[SectionData],
) -> str:
    return read_document_chunk(0, n - 1, sections)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def dispatch_tool(
    tool_name: str,
    args: dict[str, Any],
    doc_map: dict[str, DocContext],
    sections_by_doc: dict[str, list[SectionData]],
) -> str:
    doc_id = str(args.get("doc_id", ""))
    sections = sections_by_doc.get(doc_id, [])

    result: object
    match tool_name:
        case "get_document_metadata":
            result = get_document_metadata(doc_id, doc_map, sections)
        case "get_document_outline":
            result = get_document_outline(sections)
        case "search_document":
            result = search_document(str(args.get("query", "")), sections)
        case "read_document_section":
            result = read_document_section(int(args.get("section_index") or 0), sections)
        case "read_document_chunk":
            result = read_document_chunk(
                int(args.get("start_index") or 0),
                int(args.get("end_index") or 0),
                sections,
            )
        case "read_document_head":
            result = read_document_head(int(args.get("n") or 3), sections)
        case _:
            result = {"error": f"Unknown tool: {tool_name!r}"}

    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# OpenAI-compatible tool schemas for the sub-agent
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "get_document_metadata",
            "description": (
                "Get metadata for a document: filename, number of sections, total token count."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "The document ID"},
                },
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_outline",
            "description": (
                "Get a list of all sections in a document: index, heading, and token count."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "The document ID"},
                },
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_document",
            "description": (
                "Case-insensitive keyword search across all sections of a document. "
                "Returns matching sections with surrounding snippet text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "The document ID"},
                    "query": {
                        "type": "string",
                        "description": "Keyword or phrase to search for",
                    },
                },
                "required": ["doc_id", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document_section",
            "description": "Read the full content of a specific section by its index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "The document ID"},
                    "section_index": {
                        "type": "integer",
                        "description": "The section index (from get_document_outline)",
                    },
                },
                "required": ["doc_id", "section_index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document_chunk",
            "description": "Read a contiguous range of sections (start_index to end_index inclusive).",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "The document ID"},
                    "start_index": {
                        "type": "integer",
                        "description": "First section index (inclusive)",
                    },
                    "end_index": {
                        "type": "integer",
                        "description": "Last section index (inclusive)",
                    },
                },
                "required": ["doc_id", "start_index", "end_index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document_head",
            "description": "Read the first N sections of a document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "The document ID"},
                    "n": {
                        "type": "integer",
                        "description": "Number of sections to read from the beginning (default 3)",
                    },
                },
                "required": ["doc_id"],
            },
        },
    },
]
