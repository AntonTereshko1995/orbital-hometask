from __future__ import annotations

from services.document_index import ParsedSection, parse_sections

MODEL = "anthropic/claude-haiku-4-5-20251001"


def test_parse_sections_empty() -> None:
    result = parse_sections("", MODEL)
    assert result == []


def test_parse_sections_whitespace_only() -> None:
    result = parse_sections("   \n\n   ", MODEL)
    assert result == []


def test_parse_sections_with_legal_headings() -> None:
    text = (
        "Section 1 — Definitions\n\n"
        "The Lessee shall pay monthly rent.\n\n"
        "Section 2 — Demise\n\n"
        "The landlord hereby demises the premises.\n"
    )
    sections = parse_sections(text, MODEL)
    assert len(sections) == 2
    assert sections[0].heading == "Section 1 — Definitions"
    assert sections[1].heading == "Section 2 — Demise"
    assert "rent" in sections[0].content
    assert "demises" in sections[1].content
    assert all(s.token_count > 0 for s in sections)
    assert sections[0].index == 0
    assert sections[1].index == 1


def test_parse_sections_strips_page_noise() -> None:
    text = (
        "Section 1 — Definitions\n\n"
        "Content one.\n"
        "Page 1\n"
        "Section 2 — Demise\n\n"
        "Content two.\n"
    )
    sections = parse_sections(text, MODEL)
    # "Page 1" should be stripped so exactly 2 sections are found
    assert len(sections) == 2
    assert sections[0].heading == "Section 1 — Definitions"
    assert sections[1].heading == "Section 2 — Demise"


def test_parse_sections_without_headings_falls_back() -> None:
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    sections = parse_sections(text, MODEL)
    assert len(sections) >= 1
    assert all(s.heading is None for s in sections)
    # All content must be present somewhere
    combined = " ".join(s.content for s in sections)
    assert "First paragraph" in combined
    assert "Third paragraph" in combined


def test_parse_sections_paragraph_fallback_preserves_content() -> None:
    text = "\n\n".join(f"Paragraph {i} with some legal text about lease terms." for i in range(5))
    sections = parse_sections(text, MODEL)
    assert len(sections) >= 1
    combined = " ".join(s.content for s in sections)
    assert "Paragraph 0" in combined
    assert "Paragraph 4" in combined


def test_parse_sections_article_heading() -> None:
    text = "ARTICLE I — GENERAL PROVISIONS\n\nSome general provisions.\n\nARTICLE II — RENT\n\nRent details.\n"
    sections = parse_sections(text, MODEL)
    assert len(sections) == 2
    assert sections[0].heading == "ARTICLE I — GENERAL PROVISIONS"
    assert sections[1].heading == "ARTICLE II — RENT"


def test_parse_sections_schedule_heading() -> None:
    text = "Schedule 1 — Plan of Premises\n\nThe premises are shown on the attached plan.\n"
    sections = parse_sections(text, MODEL)
    assert len(sections) == 1
    assert sections[0].heading == "Schedule 1 — Plan of Premises"


def test_parse_sections_indices_are_sequential() -> None:
    text = (
        "Section 1 — Alpha\n\nContent A.\n\n"
        "Section 2 — Beta\n\nContent B.\n\n"
        "Section 3 — Gamma\n\nContent C.\n"
    )
    sections = parse_sections(text, MODEL)
    assert [s.index for s in sections] == list(range(len(sections)))


def test_parsed_section_is_dataclass() -> None:
    ps = ParsedSection(index=0, heading="Test", content="content", token_count=3)
    assert ps.index == 0
    assert ps.heading == "Test"
    assert ps.content == "content"
    assert ps.token_count == 3
