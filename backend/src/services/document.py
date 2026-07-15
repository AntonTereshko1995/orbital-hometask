from __future__ import annotations

import os
import uuid
from typing import Any

import structlog
from fastapi import UploadFile
from markitdown import MarkItDown  # type: ignore[import-untyped]
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from ai.embeddings import generate_and_save_embeddings
from config import settings
from db.models import Document, DocumentSection
from db.repositories import DocumentRepository, DocumentSectionRepository
from services.document_index import ParsedSection, parse_sections

logger = structlog.get_logger()

_md: Any = MarkItDown()  # pyright: ignore[reportUnknownVariableType]


def _validate_pdf(file: UploadFile, content: bytes) -> None:
    """Raise ValueError for non-PDF or oversized files."""
    is_pdf_content_type = file.content_type in ("application/pdf", "application/x-pdf")
    is_pdf_extension = (file.filename or "").lower().endswith(".pdf")
    if not is_pdf_content_type and not is_pdf_extension:
        raise ValueError("Only PDF files are supported.")
    if len(content) > settings.max_upload_size:
        raise ValueError(
            f"File too large. Maximum size is {settings.max_upload_size // (1024 * 1024)}MB."
        )


def _save_file(content: bytes, original_filename: str) -> str:
    """Write content to the upload directory and return the file path."""
    unique_name = f"{uuid.uuid4().hex}_{original_filename}"
    file_path = os.path.join(settings.upload_dir, unique_name)
    os.makedirs(settings.upload_dir, exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)
    return file_path


def _get_page_count(file_path: str) -> int:
    """Return PDF page count. Returns 0 on any error."""
    try:
        reader = PdfReader(file_path)
        return len(reader.pages)
    except Exception:
        return 0


def _extract_text(file_path: str, filename: str) -> tuple[str, int]:
    """Extract text and page count from a document. Returns (text, page_count)."""
    try:
        result: Any = _md.convert(file_path)
        text: str = str(result.markdown or "")  # .text_content is deprecated; use .markdown
        page_count = _get_page_count(file_path)
        return text, page_count
    except Exception:
        logger.exception("Failed to extract text from file", filename=filename)
        return "", 0


async def upload_document(
    session: AsyncSession, conversation_id: str, file: UploadFile
) -> Document:
    """Upload and process a PDF document for a conversation.

    Validates the file, saves to disk, extracts text, stores metadata in DB,
    indexes the document into sections for Level 2 search, and generates
    embeddings for Level 3 semantic search.
    Raises ValueError if the file is not a valid PDF.
    """
    repo = DocumentRepository(session)

    content = await file.read()
    _validate_pdf(file, content)

    original_filename = file.filename or "document.pdf"
    file_path = _save_file(content, original_filename)
    logger.info("Saved uploaded PDF", filename=original_filename, path=file_path, size=len(content))

    extracted_text, page_count = _extract_text(file_path, original_filename)
    logger.info(
        "Extracted text from PDF",
        filename=original_filename,
        page_count=page_count,
        text_length=len(extracted_text),
    )

    document = Document(
        conversation_id=conversation_id,
        filename=original_filename,
        file_path=file_path,
        extracted_text=extracted_text if extracted_text else None,
        page_count=page_count,
    )
    await repo.save(document)

    # Parse sections once — reused by both the DB index and the embedding index.
    parsed = parse_sections(extracted_text) if extracted_text else []

    await _index_sections(session, document.id, parsed)

    embedding_path = await generate_and_save_embeddings(
        document.id, parsed, settings.upload_dir
    )
    if embedding_path:
        document.embedding_path = embedding_path
        await repo.save(document)

    return document


async def _index_sections(
    session: AsyncSession, document_id: str, parsed: list[ParsedSection]
) -> None:
    """Persist pre-parsed sections to DB. Errors are logged, never raised."""
    if not parsed:
        return
    try:
        section_repo = DocumentSectionRepository(session)
        sections = [
            DocumentSection(
                document_id=document_id,
                section_index=ps.index,
                heading=ps.heading,
                content=ps.content,
                token_count=ps.token_count,
            )
            for ps in parsed
        ]
        await section_repo.save_bulk(sections)
        logger.info("Indexed document sections", document_id=document_id, count=len(sections))
    except Exception:
        logger.exception("Failed to index sections", document_id=document_id)
