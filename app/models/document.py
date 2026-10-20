"""Document and version data structures."""

from dataclasses import dataclass


@dataclass
class DocumentVersion:
    document_id: str
    filename: str
    version: str
    merkle_root: str
    active: bool


@dataclass
class IngestionResult:
    document_id: str
    filename: str
    version: str
    chunk_count: int
    merkle_root: str
    unchanged: bool = False
