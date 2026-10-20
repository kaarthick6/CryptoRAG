"""Canonical SHA-256 hashing for chunk text and metadata."""

import hashlib
import hmac
import json


def calculate_hash(content: bytes | str) -> str:
    """Return a hexadecimal SHA-256 digest using UTF-8 for string input."""
    content_bytes = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(content_bytes).hexdigest()


def canonical_chunk_content(chunk) -> bytes:
    """Serialize exact chunk text and identifying metadata deterministically."""
    fields = {
        "chunk_id": get_value(chunk, "chunk_id"),
        "document_id": get_value(chunk, "document_id"),
        "filename": get_value(chunk, "filename"),
        "version": get_value(chunk, "version"),
        "page_number": get_value(chunk, "page_number"),
        "text": get_value(chunk, "text"),
    }
    return json.dumps(fields, ensure_ascii=False, sort_keys=True).encode("utf-8")


def get_value(chunk, field: str):
    """Read a field from either a model object or a dictionary."""
    if isinstance(chunk, dict):
        return chunk.get(field)
    return getattr(chunk, field)


def calculate_chunk_hash(chunk) -> str:
    """Hash the canonical chunk text and metadata representation."""
    return calculate_hash(canonical_chunk_content(chunk))


def verify_chunk_hash(chunk, expected_hash: str) -> bool:
    """Compare a recalculated chunk digest with its trusted stored digest."""
    actual_hash = calculate_chunk_hash(chunk)
    return hmac.compare_digest(actual_hash, expected_hash)
