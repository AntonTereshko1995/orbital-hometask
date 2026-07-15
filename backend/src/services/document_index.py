from __future__ import annotations

import re
from dataclasses import dataclass

# Matches legal document section headings as produced by MarkItDown for PDFs.
# MarkItDown outputs plain text (not markdown # headings), so we detect structural
# patterns specific to CRE legal documents:
#   "Section 1 — Definitions and Interpretation"
#   "ARTICLE I — RENT"
#   "Schedule 1 — Plan"
# The em dash character (—, U+2014) is what pdfminer/pdfplumber preserves.
_LEGAL_HEADING_RE = re.compile(
    r"^("
    r"Section \d+[\s—\-].*"
    r"|ARTICLE [IVX\d]+[\s—\-].*"
    r"|Schedule \d+.*"
    r"|Appendix \d+.*"
    r")",
    re.MULTILINE,
)

# pdfminer injects "Page N" lines as bare text — strip them before parsing.
_PAGE_NOISE_RE = re.compile(r"\nPage \d+\n", re.MULTILINE)

# Maximum words to accumulate per section before starting a new one (paragraph fallback).
# Token counts are approximated as word counts (~1 word ≈ 1.3 LLM tokens).
_MAX_SECTION_WORDS = 1000


@dataclass
class ParsedSection:
    index: int
    heading: str | None
    content: str
    token_count: int  # approximated as word count; used for chunking and size estimates


def _preprocess(text: str) -> str:
    return _PAGE_NOISE_RE.sub("\n", text).strip()


def parse_sections(text: str) -> list[ParsedSection]:
    """Parse document text into logical sections.

    First attempts heading-based splitting using legal document patterns
    (Section N, ARTICLE, Schedule). Falls back to paragraph-budget chunking
    when no headings are detected.

    token_count on each section is approximated as word count (no LLM call needed).
    """
    if not text.strip():
        return []

    text = _preprocess(text)
    heading_matches = list(_LEGAL_HEADING_RE.finditer(text))

    if heading_matches:
        sections = _split_by_headings(text, heading_matches)
        if sections:
            return sections

    return _split_by_paragraphs(text)


def _split_by_headings(
    text: str,
    matches: list[re.Match[str]],
) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    for i, m in enumerate(matches):
        heading = m.group(0).strip()
        content_start = m.end()
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[content_start:content_end].strip()
        if not content:
            continue
        tc = max(1, len(content.split()))
        sections.append(
            ParsedSection(
                index=len(sections),
                heading=heading,
                content=content,
                token_count=tc,
            )
        )
    return sections


def _split_by_paragraphs(text: str) -> list[ParsedSection]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    sections: list[ParsedSection] = []
    buf: list[str] = []
    buf_tokens = 0

    for para in paragraphs:
        pt: int = max(1, len(para.split()))
        if buf and buf_tokens + pt > _MAX_SECTION_WORDS:
            sections.append(
                ParsedSection(
                    index=len(sections),
                    heading=None,
                    content="\n\n".join(buf),
                    token_count=buf_tokens,
                )
            )
            buf, buf_tokens = [], 0
        buf.append(para)
        buf_tokens += pt

    if buf:
        sections.append(
            ParsedSection(
                index=len(sections),
                heading=None,
                content="\n\n".join(buf),
                token_count=buf_tokens,
            )
        )
    return sections
