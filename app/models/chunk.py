"""Chunk metadata and verified-context structures."""

from dataclasses import dataclass


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    filename: str
    version: str
    page_number: int
    text: str
    content_hash: str
    proof: list[dict]


@dataclass(frozen=True)
class VerifiedChunk:
    chunk_id: str
    document_id: str
    filename: str
    version: str
    page_number: int
    text: str
