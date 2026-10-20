"""Tests for signed local root manifests."""

import json

import pytest

from app.config import get_settings
from app.services.manifest_service import (
    create_manifest,
    load_trusted_document_root,
    save_manifest,
    update_manifest_document,
    verify_manifest_signature,
)


def test_manifest_signature_validates_and_modified_manifest_fails():
    manifest = create_manifest(
        [{"document_id": "doc-1", "version": "v1", "merkle_root": "a" * 64}]
    )
    assert verify_manifest_signature(manifest)

    manifest["documents"][0]["merkle_root"] = "b" * 64
    assert not verify_manifest_signature(manifest)


def test_wrong_signing_key_fails(monkeypatch):
    manifest = create_manifest(
        [{"document_id": "doc-1", "version": "v1", "merkle_root": "a" * 64}]
    )
    monkeypatch.setenv("MANIFEST_SIGNING_KEY", "different-secret-key-at-least-32-bytes")
    get_settings.cache_clear()
    assert not verify_manifest_signature(manifest)


def test_signed_root_can_be_loaded_and_modified_file_is_rejected(tmp_path):
    settings = get_settings()
    manifest = create_manifest(
        [{"document_id": "doc-1", "version": "v1", "merkle_root": "a" * 64}]
    )
    save_manifest(manifest)
    assert load_trusted_document_root("doc-1", "v1") == "a" * 64

    altered = json.loads(settings.manifest_path.read_text())
    altered["documents"][0]["merkle_root"] = "b" * 64
    settings.manifest_path.write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="Tampered or unverified context"):
        load_trusted_document_root("doc-1", "v1")


def test_missing_signing_key_fails_closed(monkeypatch):
    monkeypatch.delenv("MANIFEST_SIGNING_KEY")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="MANIFEST_SIGNING_KEY"):
        create_manifest([])


def test_new_version_keeps_prior_signed_root():
    old_root = "aa" * 32
    new_root = "bb" * 32
    save_manifest(
        create_manifest(
            [{"document_id": "doc-1", "version": "v1", "merkle_root": old_root}]
        )
    )
    update_manifest_document(
        {"document_id": "doc-1", "version": "v2", "merkle_root": new_root},
        "doc-1",
    )

    assert load_trusted_document_root("doc-1", "v1") == old_root
    assert load_trusted_document_root("doc-1", "v2") == new_root
