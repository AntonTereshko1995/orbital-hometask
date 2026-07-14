from __future__ import annotations

import os
import uuid
from typing import Any

import structlog
from fastapi import UploadFile
from markitdown import MarkItDown  # type: ignore[import-untyped]
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models import Document

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
        text: str = str(result.text_content or "")
        page_count = _get_page_count(file_path)
        return text, page_count
    except Exception:
        logger.exception("Failed to extract text from file", filename=filename)
        return "", 0


async def upload_document(
    session: AsyncSession, conversation_id: str, file: UploadFile
) -> Document:
    """Upload and process a PDF document for a conversation.

    Validates the file, saves to disk, extracts text, and stores metadata in DB.
    Raises ValueError if the conversation already has a document or file is not a PDF.
    """
    existing = await get_document_for_conversation(session, conversation_id)
    if existing is not None:
        raise ValueError("Conversation already has a document. Only one document per conversation is allowed.")

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
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


async def get_document(session: AsyncSession, document_id: str) -> Document | None:
    """Get a document by its ID."""
    stmt = select(Document).where(Document.id == document_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_document_for_conversation(
    session: AsyncSession, conversation_id: str
) -> Document | None:
    """Get the document for a conversation, if one exists."""
    stmt = select(Document).where(Document.conversation_id == conversation_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
