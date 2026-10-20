"""HMAC-signed local trust manifest for expected document roots."""

import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path

from app.config import get_settings


def canonical_manifest_data(documents: list[dict]) -> bytes:
    """Serialize document identity, version, and root in a stable order."""
    canonical_documents = sorted(
        [
            {
                "document_id": document["document_id"],
                "version": document["version"],
                "merkle_root": document["merkle_root"],
            }
            for document in documents
        ],
        key=lambda item: (item["document_id"], item["version"]),
    )
    return json.dumps(
        canonical_documents, sort_keys=True, separators=(",", ":")
    ).encode()


def get_signing_key() -> bytes:
    """Return the configured secret or fail when trusted roots cannot be signed."""
    key = get_settings().manifest_signing_key
    if not key or len(key.encode("utf-8")) < 32:
        raise RuntimeError("MANIFEST_SIGNING_KEY must contain at least 32 characters")
    return key.encode("utf-8")


def sign_manifest(documents: list[dict]) -> str:
    """Create a SHA-256 HMAC over the canonical manifest data."""
    signature = hmac.new(
        get_signing_key(), canonical_manifest_data(documents), hashlib.sha256
    )
    return signature.hexdigest()


def create_manifest(documents: list[dict]) -> dict:
    """Return a new manifest and its signature for deliberate ingestion updates."""
    return {"documents": documents, "signature": sign_manifest(documents)}


def verify_manifest_signature(manifest: dict) -> bool:
    """Verify the HMAC without changing or re-signing the stored manifest."""
    try:
        expected_signature = sign_manifest(manifest["documents"])
        return hmac.compare_digest(expected_signature, manifest["signature"])
    except (KeyError, TypeError, RuntimeError):
        return False


def load_manifest() -> dict:
    """Load and authenticate the manifest, failing closed on missing or bad data."""
    get_signing_key()
    manifest_path = get_settings().manifest_path
    if not manifest_path.exists():
        raise RuntimeError("Trusted manifest is missing; ingest documents to create it")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Trusted manifest could not be read") from error
    if not verify_manifest_signature(manifest):
        raise ValueError("Tampered or unverified context")
    return manifest


def load_trusted_document_root(document_id: str, version: str) -> str:
    """Return the signed root for one document version or fail closed."""
    manifest = load_manifest()
    for document in manifest["documents"]:
        if (
            document.get("document_id") == document_id
            and document.get("version") == version
        ):
            return document["merkle_root"]
    raise ValueError("Tampered or unverified context")


def update_manifest_document(document: dict | None, document_id: str) -> dict:
    """Deliberately add or replace one root, or remove a document root."""
    manifest_path = get_settings().manifest_path
    if manifest_path.exists():
        current_manifest = load_manifest()
        if document is None:
            documents = [
                item for item in current_manifest["documents"]
                if item["document_id"] != document_id
            ]
        else:
            documents = [
                item for item in current_manifest["documents"]
                if not (
                    item["document_id"] == document_id
                    and item["version"] == document["version"]
                )
            ]
    else:
        get_signing_key()
        documents = []

    if document is not None:
        documents.append(document)
    updated_manifest = create_manifest(documents)
    save_manifest(updated_manifest)
    return updated_manifest


def save_manifest(manifest: dict) -> None:
    """Atomically write a deliberately created signed manifest."""
    manifest_path = get_settings().manifest_path
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=manifest_path.parent,
            delete=False, suffix=".tmp",
        ) as temporary_file:
            json.dump(manifest, temporary_file, indent=2, sort_keys=True)
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, manifest_path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
