"""Tests for the complete stored chunk verification sequence."""

import json

import pytest

from app.config import get_settings
from app.models.chunk import Chunk
from app.repositories.metadata_repository import MetadataRepository
from app.services.hashing_service import calculate_chunk_hash
from app.services.manifest_service import create_manifest, save_manifest
from app.services.merkle_service import (
    build_merkle_tree,
    create_merkle_proof,
    get_merkle_root,
)
from app.services.verification_service import verify_chunk


def create_stored_chunk(repository, text="policy text", version="v1"):
    chunk = Chunk("chunk-1", "doc-1", "policy.pdf", version, 1, text, "", [])
    chunk.content_hash = calculate_chunk_hash(chunk)
    tree = build_merkle_tree([chunk.content_hash])
    root = get_merkle_root(tree)
    chunk.proof = create_merkle_proof(tree, 0)
    repository.save_document_version("doc-1", "policy.pdf", version, root, [chunk])
    manifest = create_manifest(
        [{"document_id": "doc-1", "version": version, "merkle_root": root}]
    )
    save_manifest(manifest)
    return chunk


def test_valid_chunk_passes_hash_version_manifest_and_merkle_checks():
    repository = MetadataRepository()
    chunk = create_stored_chunk(repository)

    verified_chunk = verify_chunk(chunk, repository)

    assert verified_chunk.chunk_id == chunk.chunk_id
    assert verified_chunk.text == chunk.text


def test_invalid_proof_fails_verification():
    repository = MetadataRepository()
    chunk = create_stored_chunk(repository)
    chunk.proof = [{"side": "right", "hash": "00" * 32}]
    with repository.connection() as connection:
        invalid_proof = [{"side": "right", "hash": "00" * 32}]
        connection.execute(
            "UPDATE chunks SET proof_json = ?", (json.dumps(invalid_proof),)
        )

    with pytest.raises(ValueError, match="Tampered or unverified context"):
        verify_chunk(chunk, repository)


def test_modified_chunk_text_fails_verification():
    repository = MetadataRepository()
    chunk = create_stored_chunk(repository)
    with repository.connection() as connection:
        connection.execute("UPDATE chunks SET text = ?", ("modified policy",))

    with pytest.raises(ValueError, match="Tampered or unverified context"):
        verify_chunk(chunk, repository)


def test_deactivated_document_version_fails():
    repository = MetadataRepository()
    chunk = create_stored_chunk(repository)
    repository.deactivate_document(chunk.document_id)

    with pytest.raises(ValueError, match="Tampered or unverified context"):
        verify_chunk(chunk, repository)


def test_database_root_modified_from_signed_root_fails():
    repository = MetadataRepository()
    chunk = create_stored_chunk(repository)
    with repository.connection() as connection:
        connection.execute(
            "UPDATE document_versions SET merkle_root = ?", ("ff" * 32,)
        )

    with pytest.raises(ValueError, match="Tampered or unverified context"):
        verify_chunk(chunk, repository)


def test_modified_manifest_prevents_verification():
    repository = MetadataRepository()
    chunk = create_stored_chunk(repository)
    manifest_path = get_settings().manifest_path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["documents"][0]["merkle_root"] = "ab" * 32
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Tampered or unverified context"):
        verify_chunk(chunk, repository)
