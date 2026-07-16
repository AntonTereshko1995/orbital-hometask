from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.document import _extract_text, _get_page_count, _save_file, _validate_pdf

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upload_file(
    content_type: str = "application/pdf",
    filename: str = "test.pdf",
) -> MagicMock:
    f = MagicMock()
    f.content_type = content_type
    f.filename = filename
    return f


_PDF_BYTES = b"%PDF-1.4 fake content"
_BIG_BYTES = b"x" * (25 * 1024 * 1024 + 1)  # 1 byte over the 25 MB limit


# ---------------------------------------------------------------------------
# _validate_pdf
# ---------------------------------------------------------------------------


def test_validate_pdf_ok_by_content_type() -> None:
    _validate_pdf(_upload_file(content_type="application/pdf"), _PDF_BYTES)


def test_validate_pdf_ok_by_x_pdf_content_type() -> None:
    _validate_pdf(_upload_file(content_type="application/x-pdf"), _PDF_BYTES)


def test_validate_pdf_ok_by_extension_only() -> None:
    # content_type is not PDF but filename ends in .pdf
    _validate_pdf(_upload_file(content_type="application/octet-stream", filename="lease.pdf"), _PDF_BYTES)


def test_validate_pdf_rejects_non_pdf() -> None:
    with pytest.raises(ValueError, match="Only PDF files are supported"):
        _validate_pdf(_upload_file(content_type="text/plain", filename="doc.txt"), _PDF_BYTES)


def test_validate_pdf_rejects_oversized_file() -> None:
    with pytest.raises(ValueError, match="File too large"):
        _validate_pdf(_upload_file(), _BIG_BYTES)


def test_validate_pdf_rejects_oversized_even_if_valid_type() -> None:
    with pytest.raises(ValueError, match="File too large"):
        _validate_pdf(
            _upload_file(content_type="application/pdf", filename="big.pdf"),
            _BIG_BYTES,
        )


# ---------------------------------------------------------------------------
# _save_file
# ---------------------------------------------------------------------------


def test_save_file_creates_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.document.settings",
        MagicMock(upload_dir=str(tmp_path), max_upload_size=25 * 1024 * 1024),
    )
    path = _save_file(_PDF_BYTES, "lease.pdf")
    assert os.path.exists(path)
    assert open(path, "rb").read() == _PDF_BYTES


def test_save_file_returns_path_inside_upload_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "services.document.settings",
        MagicMock(upload_dir=str(tmp_path), max_upload_size=25 * 1024 * 1024),
    )
    path = _save_file(_PDF_BYTES, "contract.pdf")
    assert path.startswith(str(tmp_path))


def test_save_file_generates_unique_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "services.document.settings",
        MagicMock(upload_dir=str(tmp_path), max_upload_size=25 * 1024 * 1024),
    )
    path1 = _save_file(_PDF_BYTES, "lease.pdf")
    path2 = _save_file(_PDF_BYTES, "lease.pdf")
    assert path1 != path2


# ---------------------------------------------------------------------------
# _get_page_count
# ---------------------------------------------------------------------------


def test_get_page_count_returns_zero_on_invalid_path() -> None:
    result = _get_page_count("/nonexistent/file.pdf")
    assert result == 0


# ---------------------------------------------------------------------------
# _extract_text
# ---------------------------------------------------------------------------


def test_extract_text_returns_empty_on_exception() -> None:
    mock_md = MagicMock()
    mock_md.convert.side_effect = RuntimeError("conversion failed")

    with patch("services.document._md", mock_md):
        text, pages = _extract_text("/any/path.pdf", "doc.pdf")

    assert text == ""
    assert pages == 0


def test_extract_text_returns_markdown_content(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(_PDF_BYTES)

    mock_result = MagicMock()
    mock_result.markdown = "# Section 1\n\nRent is £5,000 per month."

    mock_md = MagicMock()
    mock_md.convert.return_value = mock_result

    with patch("services.document._md", mock_md):
        with patch("services.document._get_page_count", return_value=3):
            text, pages = _extract_text(str(pdf_path), "test.pdf")

    assert "Rent" in text
    assert pages == 3


def test_extract_text_handles_none_markdown(tmp_path: Path) -> None:
    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    mock_result = MagicMock()
    mock_result.markdown = None  # MarkItDown may return None

    mock_md = MagicMock()
    mock_md.convert.return_value = mock_result

    with patch("services.document._md", mock_md):
        with patch("services.document._get_page_count", return_value=1):
            text, pages = _extract_text(str(pdf_path), "empty.pdf")

    assert text == ""
    assert pages == 1
