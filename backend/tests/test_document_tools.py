from __future__ import annotations

import json

from ai.document_tools import (
    DocContext,
    SectionData,
    dispatch_tool,
    get_document_metadata,
    get_document_outline,
    read_document_chunk,
    read_document_head,
    read_document_section,
    search_document,
)

SECTIONS: list[SectionData] = [
    SectionData(
        id="s0",
        doc_id="d1",
        index=0,
        heading="Definitions",
        content="The Lessee shall pay monthly rent to the Landlord.",
        token_count=10,
    ),
    SectionData(
        id="s1",
        doc_id="d1",
        index=1,
        heading="Term",
        content="The lease term is ten (10) years commencing on 1 January 2024.",
        token_count=14,
    ),
    SectionData(
        id="s2",
        doc_id="d1",
        index=2,
        heading=None,
        content="Additional provisions apply.",
        token_count=4,
    ),
]

DOC_MAP: dict[str, DocContext] = {
    "d1": DocContext(id="d1", filename="commercial-lease.pdf", text="full text here"),
}

SECTIONS_BY_DOC: dict[str, list[SectionData]] = {"d1": SECTIONS}


# ---------------------------------------------------------------------------
# get_document_metadata
# ---------------------------------------------------------------------------


def test_get_metadata_known_doc() -> None:
    result = get_document_metadata("d1", DOC_MAP, SECTIONS)
    assert result["id"] == "d1"
    assert result["filename"] == "commercial-lease.pdf"
    assert result["section_count"] == 3
    assert result["total_tokens"] == 28


def test_get_metadata_unknown_doc() -> None:
    result = get_document_metadata("unknown", DOC_MAP, [])
    assert "error" in result


# ---------------------------------------------------------------------------
# get_document_outline
# ---------------------------------------------------------------------------


def test_get_outline_returns_all_sections() -> None:
    outline = get_document_outline(SECTIONS)
    assert len(outline) == 3
    assert outline[0]["index"] == 0
    assert outline[0]["heading"] == "Definitions"
    assert outline[1]["index"] == 1
    assert outline[1]["heading"] == "Term"


def test_get_outline_none_heading_uses_block_label() -> None:
    outline = get_document_outline(SECTIONS)
    # Third section has heading=None → should get "Block 2"
    assert outline[2]["heading"] == "Block 2"


def test_get_outline_empty_sections() -> None:
    assert get_document_outline([]) == []


# ---------------------------------------------------------------------------
# search_document
# ---------------------------------------------------------------------------


def test_search_hit_case_insensitive() -> None:
    results = search_document("RENT", SECTIONS)
    assert len(results) == 1
    assert results[0]["section_index"] == 0
    assert "rent" in results[0]["snippet"].lower()  # type: ignore[operator]


def test_search_miss() -> None:
    results = search_document("nonexistent_xyz_abc", SECTIONS)
    assert results == []


def test_search_multiple_hits() -> None:
    results = search_document("the", SECTIONS)
    assert len(results) >= 1


def test_search_returns_at_most_10() -> None:
    many_sections: list[SectionData] = [
        SectionData(id=f"s{i}", doc_id="d1", index=i, heading=None, content="the keyword here", token_count=3)
        for i in range(20)
    ]
    results = search_document("keyword", many_sections)
    assert len(results) <= 10


# ---------------------------------------------------------------------------
# read_document_section
# ---------------------------------------------------------------------------


def test_read_section_with_heading() -> None:
    text = read_document_section(0, SECTIONS)
    assert "Definitions" in text
    assert "Lessee" in text


def test_read_section_without_heading() -> None:
    text = read_document_section(2, SECTIONS)
    assert "Additional provisions" in text
    # No heading prefix expected
    assert "##" not in text


def test_read_section_not_found() -> None:
    text = read_document_section(999, SECTIONS)
    assert "not found" in text.lower()


# ---------------------------------------------------------------------------
# read_document_chunk
# ---------------------------------------------------------------------------


def test_read_chunk_range() -> None:
    text = read_document_chunk(0, 1, SECTIONS)
    assert "Definitions" in text
    assert "Term" in text
    assert "Additional" not in text


def test_read_chunk_single_section() -> None:
    text = read_document_chunk(1, 1, SECTIONS)
    assert "Term" in text
    assert "Definitions" not in text


def test_read_chunk_empty_range() -> None:
    text = read_document_chunk(50, 60, SECTIONS)
    assert "No sections found" in text


# ---------------------------------------------------------------------------
# read_document_head
# ---------------------------------------------------------------------------


def test_read_head_n_2() -> None:
    text = read_document_head(2, SECTIONS)
    assert "Definitions" in text
    assert "Term" in text
    assert "Additional" not in text


def test_read_head_n_1() -> None:
    text = read_document_head(1, SECTIONS)
    assert "Definitions" in text
    assert "Term" not in text


# ---------------------------------------------------------------------------
# dispatch_tool
# ---------------------------------------------------------------------------


def test_dispatch_get_metadata() -> None:
    raw = dispatch_tool("get_document_metadata", {"doc_id": "d1"}, DOC_MAP, SECTIONS_BY_DOC)
    data = json.loads(raw)
    assert data["filename"] == "commercial-lease.pdf"


def test_dispatch_get_outline() -> None:
    raw = dispatch_tool("get_document_outline", {"doc_id": "d1"}, DOC_MAP, SECTIONS_BY_DOC)
    data = json.loads(raw)
    assert isinstance(data, list)
    assert len(data) == 3


def test_dispatch_search() -> None:
    raw = dispatch_tool(
        "search_document", {"doc_id": "d1", "query": "rent"}, DOC_MAP, SECTIONS_BY_DOC
    )
    data = json.loads(raw)
    assert isinstance(data, list)
    assert len(data) == 1


def test_dispatch_read_section() -> None:
    raw = dispatch_tool(
        "read_document_section", {"doc_id": "d1", "section_index": 0}, DOC_MAP, SECTIONS_BY_DOC
    )
    assert "Definitions" in raw


def test_dispatch_read_chunk() -> None:
    raw = dispatch_tool(
        "read_document_chunk",
        {"doc_id": "d1", "start_index": 0, "end_index": 1},
        DOC_MAP,
        SECTIONS_BY_DOC,
    )
    assert "Definitions" in raw
    assert "Term" in raw


def test_dispatch_read_head() -> None:
    raw = dispatch_tool("read_document_head", {"doc_id": "d1", "n": 1}, DOC_MAP, SECTIONS_BY_DOC)
    assert "Definitions" in raw


def test_dispatch_unknown_tool() -> None:
    raw = dispatch_tool("nonexistent_tool", {"doc_id": "d1"}, DOC_MAP, SECTIONS_BY_DOC)
    data = json.loads(raw)
    assert "error" in data


def test_dispatch_missing_doc_id_returns_gracefully() -> None:
    raw = dispatch_tool("get_document_outline", {"doc_id": "does_not_exist"}, DOC_MAP, SECTIONS_BY_DOC)
    data = json.loads(raw)
    assert isinstance(data, list)
    assert data == []
