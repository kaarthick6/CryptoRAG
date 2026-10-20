"""PDF opening and page-by-page text extraction using PyMuPDF."""

from pathlib import Path

import fitz


def extract_pages(file_path: Path) -> list[dict]:
    """Extract non-empty page text while preserving one-based page numbers."""
    if not file_path.exists() or not file_path.is_file():
        raise ValueError(f"PDF file does not exist: {file_path.name}")
    if file_path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF files can be ingested")

    try:
        pdf_document = fitz.open(file_path)
    except (fitz.FileDataError, RuntimeError) as error:
        raise ValueError(f"Could not open PDF {file_path.name}: {error}") from error

    pages = []
    with pdf_document:
        if pdf_document.is_encrypted:
            raise ValueError(f"Encrypted PDF cannot be read: {file_path.name}")
        for page_index, page in enumerate(pdf_document, start=1):
            page_text = page.get_text("text").strip()
            if page_text:
                pages.append({"page_number": page_index, "text": page_text})

    if not pages:
        raise ValueError(f"PDF contains no extractable text: {file_path.name}")
    return pages
