"""Compatibility import for canonical chunk hashing."""

from app.services.hashing_service import calculate_chunk_hash


def add_hashes(chunks: list[dict]) -> list[dict]:
    """Return copied chunks with canonical metadata-aware hashes."""
    hashed_chunks = []
    for chunk in chunks:
        hashed_chunk = chunk.copy()
        hashed_chunk["chunk_hash"] = calculate_chunk_hash(hashed_chunk)
        hashed_chunks.append(hashed_chunk)
    return hashed_chunks
