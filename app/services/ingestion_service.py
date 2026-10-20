"""Coordinate PDF ingestion into SQLite, Whoosh, Milvus, and a signed root."""

import hashlib
from pathlib import Path

from app.config import get_settings
from app.models.chunk import Chunk
from app.models.document import IngestionResult
from app.repositories.metadata_repository import MetadataRepository
from app.services.chunking_service import create_chunks
from app.services.embedding_service import embed_chunks
from app.services.hashing_service import calculate_chunk_hash
from app.services.keyword_search import index_chunks
from app.services.manifest_service import (
    get_signing_key,
    load_manifest,
    load_trusted_document_root,
    update_manifest_document,
)
from app.services.merkle_service import (
    build_merkle_tree,
    create_merkle_proof,
    get_merkle_root,
)
from app.services.pdf_service import extract_pages
from app.services.vector_search import index_vectors, remove_document_vectors
from app.services.verification_service import verify_chunk


def create_document_id(filename: str) -> str:
    """Create a stable identifier based on the original filename."""
    return hashlib.sha256(filename.casefold().encode("utf-8")).hexdigest()[:32]


def create_document_version(file_path: Path) -> str:
    """Use the source PDF bytes to identify an unchanged document version."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def create_chunk_records(
    raw_chunks: list[dict], document_id: str, filename: str, version: str
) -> list[Chunk]:
    """Assign deterministic chunk IDs and calculate canonical chunk hashes."""
    chunks = []
    for chunk_index, raw_chunk in enumerate(raw_chunks):
        chunk_id = hashlib.sha256(
            f"{document_id}:{version}:{chunk_index}".encode("utf-8")
        ).hexdigest()
        chunk = Chunk(
            chunk_id=chunk_id,
            document_id=document_id,
            filename=filename,
            version=version,
            page_number=raw_chunk["page_number"],
            text=raw_chunk["text"],
            content_hash="",
            proof=[],
        )
        chunk.content_hash = calculate_chunk_hash(chunk)
        chunks.append(chunk)
    return chunks


def add_merkle_proofs(chunks: list[Chunk]) -> tuple[list[Chunk], str]:
    """Build one ordered Merkle tree and attach each chunk's proof."""
    tree = build_merkle_tree([chunk.content_hash for chunk in chunks])
    root = get_merkle_root(tree)
    for leaf_index, chunk in enumerate(chunks):
        chunk.proof = create_merkle_proof(tree, leaf_index)
    return chunks, root


def chunk_records_for_index(chunks: list[Chunk]) -> list[dict]:
    """Convert chunk records into the scalar fields required by search indexes."""
    return [
        {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "filename": chunk.filename,
            "version": chunk.version,
            "page_number": chunk.page_number,
            "text": chunk.text,
        }
        for chunk in chunks
    ]


def ingest_pdf(
    file_path: Path, repository: MetadataRepository | None = None
) -> IngestionResult:
    """Ingest a PDF, returning early when its current version is unchanged."""
    repository = repository or MetadataRepository()
    document_id = create_document_id(file_path.name)
    version = create_document_version(file_path)
    get_signing_key()
    if get_settings().manifest_path.exists():
        load_manifest()

    current_version = repository.get_version(document_id)
    if current_version and current_version["version"] == version:
        trusted_root = load_trusted_document_root(document_id, version)
        if trusted_root != current_version["merkle_root"]:
            raise ValueError("Tampered or unverified context")
        existing_chunks = repository.get_active_chunks(document_id)
        if len(existing_chunks) != current_version["chunk_count"]:
            raise ValueError("Tampered or unverified context")
        for chunk in existing_chunks:
            verify_chunk(chunk, repository)
        return IngestionResult(
            document_id, file_path.name, version,
            current_version["chunk_count"], current_version["merkle_root"], True,
        )

    pages = extract_pages(file_path)
    raw_chunks = create_chunks(pages)
    if not raw_chunks:
        raise ValueError(f"PDF contains no usable text: {file_path.name}")

    chunks = create_chunk_records(raw_chunks, document_id, file_path.name, version)
    chunks, merkle_root = add_merkle_proofs(chunks)
    vectors = embed_chunks([chunk.text for chunk in chunks])
    indexed_chunks = chunk_records_for_index(chunks)

    # Prepare external indexes before committing the new version to SQLite.
    remove_document_vectors(document_id)
    index_chunks(indexed_chunks)
    index_vectors(indexed_chunks, vectors)

    update_manifest_document(
        {"document_id": document_id, "version": version, "merkle_root": merkle_root},
        document_id,
    )
    repository.save_document_version(
        document_id, file_path.name, version, merkle_root, chunks
    )
    return IngestionResult(
        document_id, file_path.name, version, len(chunks), merkle_root
    )


def ingest_folder(
    repository: MetadataRepository | None = None,
) -> list[IngestionResult]:
    """Ingest every PDF in the configured input directory in name order."""
    settings = get_settings()
    settings.compliance_documents_path.mkdir(parents=True, exist_ok=True)
    repository = repository or MetadataRepository()
    results = []
    for file_path in sorted(settings.compliance_documents_path.glob("*.pdf")):
        results.append(ingest_pdf(file_path, repository))
    return results
