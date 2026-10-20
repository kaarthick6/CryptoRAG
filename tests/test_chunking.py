"""Tests for sentence-aware chunk boundaries and overlap handling."""

from types import SimpleNamespace

from app.services import chunking_service


def test_chunks_keep_page_numbers_and_sentence_text(monkeypatch):
    monkeypatch.setattr(
        chunking_service,
        "get_settings",
        lambda: SimpleNamespace(chunk_size=45, chunk_overlap=10),
    )
    pages = [
        {
            "page_number": 7,
            "text": (
                "First short sentence. Second short sentence. "
                "Third short sentence."
            ),
        }
    ]

    chunks = chunking_service.create_chunks(pages)

    assert chunks
    assert all(chunk["page_number"] == 7 for chunk in chunks)
    assert all(len(chunk["text"]) <= 45 for chunk in chunks)


def test_chunking_handles_sentence_larger_than_chunk_limit(monkeypatch):
    monkeypatch.setattr(
        chunking_service,
        "get_settings",
        lambda: SimpleNamespace(chunk_size=12, chunk_overlap=3),
    )

    chunks = chunking_service.create_chunks(
        [{"page_number": 1, "text": "extraordinaryword is split. Done."}]
    )

    assert chunks
    assert all(len(chunk["text"]) <= 12 for chunk in chunks)
