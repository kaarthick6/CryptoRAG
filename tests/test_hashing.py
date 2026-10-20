"""Tests for canonical chunk hashes."""

from app.models.chunk import Chunk
from app.services.hashing_service import calculate_chunk_hash, calculate_hash


def make_chunk(text="policy text", page_number=1):
    return Chunk(
        "chunk-1", "doc-1", "policy.pdf", "version-1", page_number, text, "", []
    )


def test_same_content_produces_same_hash():
    assert calculate_hash("policy text") == calculate_hash("policy text")


def test_modified_chunk_text_changes_hash():
    assert calculate_chunk_hash(make_chunk()) != calculate_chunk_hash(
        make_chunk("changed")
    )


def test_modified_metadata_changes_hash():
    assert calculate_chunk_hash(make_chunk()) != calculate_chunk_hash(
        make_chunk(page_number=2)
    )


def test_expected_hash_comparison_rejects_a_modified_chunk():
    from app.services.hashing_service import verify_chunk_hash

    chunk = make_chunk()
    expected_hash = calculate_chunk_hash(chunk)
    chunk.text = "changed"

    assert not verify_chunk_hash(chunk, expected_hash)
