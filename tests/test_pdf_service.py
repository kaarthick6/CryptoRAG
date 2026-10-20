"""Tests for invalid and empty PDF handling."""

import pytest

from app.services.pdf_service import extract_pages


def test_corrupt_pdf_returns_a_clear_error(tmp_path):
    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(b"not a PDF document")

    with pytest.raises(ValueError, match="Could not open PDF"):
        extract_pages(pdf_path)


def test_missing_pdf_returns_a_clear_error(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        extract_pages(tmp_path / "missing.pdf")
