"""Fail-closed chunk, active-version, signed-root, and Merkle checks."""

import logging

from app.models.chunk import Chunk, VerifiedChunk
from app.repositories.metadata_repository import MetadataRepository
from app.services.hashing_service import verify_chunk_hash
from app.services.manifest_service import load_trusted_document_root
from app.services.merkle_service import verify_merkle_proof

logger = logging.getLogger(__name__)
INTEGRITY_ERROR = "Tampered or unverified context"


def verify_chunk(chunk: Chunk, repository: MetadataRepository) -> VerifiedChunk:
    """Validate stored bytes, active version, signed root, and proof membership."""
    stored_chunk = repository.get_chunk(chunk.chunk_id)
    if stored_chunk is None or stored_chunk != chunk:
        return fail_verification(chunk.chunk_id, "chunk is missing or inactive")
    if not verify_chunk_hash(stored_chunk, stored_chunk.content_hash):
        return fail_verification(chunk.chunk_id, "chunk hash did not match")

    active_version = repository.get_version(chunk.document_id)
    if (
        active_version is None
        or active_version["version"] != chunk.version
        or not active_version["active"]
        or not active_version["document_active"]
    ):
        return fail_verification(chunk.chunk_id, "document version is not active")

    try:
        trusted_root = load_trusted_document_root(chunk.document_id, chunk.version)
    except (RuntimeError, ValueError) as error:
        logger.warning("Manifest verification failed for chunk %s", chunk.chunk_id)
        raise ValueError(INTEGRITY_ERROR) from error
    if trusted_root != active_version["merkle_root"]:
        return fail_verification(chunk.chunk_id, "trusted root did not match")
    if not verify_merkle_proof(chunk.content_hash, chunk.proof, trusted_root):
        return fail_verification(chunk.chunk_id, "Merkle inclusion proof failed")

    return VerifiedChunk(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        filename=chunk.filename,
        version=chunk.version,
        page_number=chunk.page_number,
        text=chunk.text,
    )


def verify_chunks(chunks: list[Chunk]) -> list[VerifiedChunk]:
    """Verify every selected candidate or reject the complete query context."""
    if not chunks:
        raise ValueError(INTEGRITY_ERROR)
    repository = MetadataRepository()
    verified_context = []
    for chunk in chunks:
        verified_context.append(verify_chunk(chunk, repository))
    return verified_context


def fail_verification(chunk_id: str, safe_reason: str):
    """Log an identifier and safe reason, then reject untrusted context."""
    logger.warning("Chunk %s failed integrity verification: %s", chunk_id, safe_reason)
    raise ValueError(INTEGRITY_ERROR)
