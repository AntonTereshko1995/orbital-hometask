from __future__ import annotations

import hashlib
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


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


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
        text: str = str(result.markdown or "")
        page_count = _get_page_count(file_path)
        return text, page_count
    except Exception:
        logger.exception("Failed to extract text from file", filename=filename)
        return "", 0


async def upload_to_library(
    session: AsyncSession, file: UploadFile
) -> tuple[Document, bool]:
    """Upload a PDF to the shared library (not tied to any conversation).

    Returns (document, is_duplicate). When is_duplicate is True the file already
    existed in the library and is returned as-is — no disk write or reprocessing.
    """
    doc_repo = DocumentRepository(session)

    content = await file.read()
    _validate_pdf(file, content)
    file_size = len(content)
    content_hash = _sha256(content)

    original_filename = file.filename or "document.pdf"

    existing = await doc_repo.find_duplicate(content_hash)
    if existing is not None:
        logger.info(
            "Duplicate document detected — returning library copy",
            document_id=existing.id,
            filename=original_filename,
        )
        return existing, True

    file_path = _save_file(content, original_filename)
    logger.info("Saved PDF to library", filename=original_filename, path=file_path, size=file_size)

    extracted_text, page_count = _extract_text(file_path, original_filename)
    logger.info(
        "Extracted text from PDF",
        filename=original_filename,
        page_count=page_count,
        text_length=len(extracted_text),
    )

    document = Document(
        filename=original_filename,
        file_path=file_path,
        file_size=file_size,
        content_hash=content_hash,
        extracted_text=extracted_text if extracted_text else None,
        page_count=page_count,
    )
    await doc_repo.save(document)

    parsed = parse_sections(extracted_text) if extracted_text else []
    await _index_sections(session, document.id, parsed)

    embedding_path = await generate_and_save_embeddings(document.id, parsed, settings.upload_dir)
    if embedding_path:
        document.embedding_path = embedding_path
        await doc_repo.save(document)

    return document, False


async def upload_document(
    session: AsyncSession, conversation_id: str, file: UploadFile
) -> tuple[Document, bool]:
    """Upload and process a PDF document for a conversation.

    Returns (document, reused_from_library). When reused_from_library is True
    the file already existed in the library (matched by SHA-256 content hash) and
    was simply attached to the conversation — no new file was written to disk and
    no re-processing occurred.
    """
    doc_repo = DocumentRepository(session)

    content = await file.read()
    _validate_pdf(file, content)
    file_size = len(content)
    content_hash = _sha256(content)

    original_filename = file.filename or "document.pdf"

    existing = await doc_repo.find_duplicate(content_hash)
    if existing is not None:
        await doc_repo.attach_to_conversation(existing.id, conversation_id)
        logger.info(
            "Duplicate document detected — reusing library copy",
            document_id=existing.id,
            filename=original_filename,
            conversation_id=conversation_id,
        )
        return existing, True

    file_path = _save_file(content, original_filename)
    logger.info(
        "Saved uploaded PDF",
        filename=original_filename,
        path=file_path,
        size=file_size,
    )

    extracted_text, page_count = _extract_text(file_path, original_filename)
    logger.info(
        "Extracted text from PDF",
        filename=original_filename,
        page_count=page_count,
        text_length=len(extracted_text),
    )

    document = Document(
        filename=original_filename,
        file_path=file_path,
        file_size=file_size,
        content_hash=content_hash,
        extracted_text=extracted_text if extracted_text else None,
        page_count=page_count,
    )
    await doc_repo.save(document)

    # Attach to the conversation
    await doc_repo.attach_to_conversation(document.id, conversation_id)

    # Parse sections — reused by both the DB index and the embedding index.
    parsed = parse_sections(extracted_text) if extracted_text else []

    await _index_sections(session, document.id, parsed)

    embedding_path = await generate_and_save_embeddings(
        document.id, parsed, settings.upload_dir
    )
    if embedding_path:
        document.embedding_path = embedding_path
        await doc_repo.save(document)

    return document, False


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
