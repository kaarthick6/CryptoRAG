"""Tests for document versioning and idempotent ingestion."""

import hashlib

from app.models.chunk import Chunk
from app.repositories.metadata_repository import MetadataRepository
from app.services.hashing_service import calculate_chunk_hash
from app.services.ingestion_service import (
    create_document_id,
    create_document_version,
    ingest_pdf,
)
from app.services.manifest_service import create_manifest, save_manifest
from app.services.merkle_service import (
    build_merkle_tree,
    create_merkle_proof,
    get_merkle_root,
)


def test_unchanged_document_is_idempotent(tmp_path):
    source_file = tmp_path / "policy.pdf"
    source_file.write_bytes(b"stable source file bytes")
    document_id = create_document_id(source_file.name)
    version = create_document_version(source_file)
    chunk = Chunk(
        hashlib.sha256(b"stable chunk").hexdigest(),
        document_id,
        source_file.name,
        version,
        1,
        "retention evidence",
        "",
        [],
    )
    chunk.content_hash = calculate_chunk_hash(chunk)
    tree = build_merkle_tree([chunk.content_hash])
    chunk.proof = create_merkle_proof(tree, 0)
    root = get_merkle_root(tree)
    repository = MetadataRepository()
    repository.save_document_version(
        document_id, source_file.name, version, root, [chunk]
    )
    save_manifest(
        create_manifest(
            [{"document_id": document_id, "version": version, "merkle_root": root}]
        )
    )

    result = ingest_pdf(source_file, repository)

    assert result.unchanged
    assert result.merkle_root == root
