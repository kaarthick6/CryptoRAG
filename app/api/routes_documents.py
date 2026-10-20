"""Routes for PDF uploads, ingestion, document metadata, and integrity checks."""

import logging
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.config import get_settings
from app.repositories.metadata_repository import MetadataRepository
from app.services.hashing_service import verify_chunk_hash
from app.services.ingestion_service import ingest_folder, ingest_pdf
from app.services.keyword_search import remove_document
from app.services.manifest_service import (
    load_trusted_document_root,
    update_manifest_document,
)
from app.services.merkle_service import verify_merkle_proof
from app.services.vector_search import remove_document_vectors

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


def result_to_dict(result) -> dict:
    """Convert ingestion result dataclasses into JSON response fields."""
    return {
        "document_id": result.document_id,
        "filename": result.filename,
        "version": result.version,
        "chunk_count": result.chunk_count,
        "merkle_root": result.merkle_root,
        "unchanged": result.unchanged,
    }


def validate_upload_name(filename: str | None) -> str:
    """Validate a short plain PDF filename and prevent path traversal."""
    if not filename or Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Upload needs a plain filename")
    if len(filename) > 180 or not re.fullmatch(r"[\w .()-]+\.pdf", filename, re.I):
        raise HTTPException(status_code=400, detail="Invalid PDF filename")
    return filename


@router.get("")
def list_documents() -> list[dict]:
    """List active documents and their current versions."""
    return MetadataRepository().list_documents()


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)) -> dict:
    """Validate and ingest one uploaded PDF file."""
    filename = validate_upload_name(file.filename)
    settings = get_settings()
    file_bytes = await file.read(settings.max_upload_size_mb * 1024 * 1024 + 1)
    if len(file_bytes) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF exceeds the upload size limit")
    if not file_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid PDF")

    settings.compliance_documents_path.mkdir(parents=True, exist_ok=True)
    destination = settings.compliance_documents_path / filename
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=settings.compliance_documents_path, delete=False, suffix=".pdf"
        ) as temporary_file:
            temporary_file.write(file_bytes)
            temporary_path = Path(temporary_file.name)
        temporary_path.replace(destination)
        result = ingest_pdf(destination)
    except RuntimeError as error:
        logger.warning("PDF upload could not reach a required service: %s", error)
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (ValueError, OSError) as error:
        logger.warning("PDF upload could not be ingested: %s", error)
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
    return result_to_dict(result)


@router.post("/ingest-folder")
def ingest_document_folder() -> dict:
    """Ingest the configured folder's PDF files in deterministic order."""
    try:
        results = ingest_folder()
    except RuntimeError as error:
        logger.warning("Folder ingestion service unavailable: %s", error)
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (ValueError, OSError) as error:
        logger.warning("Folder ingestion failed: %s", error)
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"documents": [result_to_dict(result) for result in results]}


@router.get("/{document_id}")
def get_document(document_id: str) -> dict:
    """Return metadata for one document, including inactive records."""
    document = MetadataRepository().get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/{document_id}")
def delete_document(document_id: str) -> dict:
    """Deactivate a document and remove it from signed and search indexes."""
    repository = MetadataRepository()
    document = repository.get_document(document_id)
    if document is None or not document["active"]:
        raise HTTPException(status_code=404, detail="Active document not found")
    try:
        update_manifest_document(None, document_id)
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    repository.deactivate_document(document_id)
    try:
        remove_document(document_id)
        remove_document_vectors(document_id)
    except RuntimeError as error:
        logger.warning("Document deactivated but search-index cleanup failed")
        raise HTTPException(
            status_code=503, detail="Search index cleanup failed"
        ) from error
    return {"message": "Document deactivated"}


@router.get("/{document_id}/integrity")
def document_integrity(
    document_id: str, version: str | None = Query(default=None)
) -> dict:
    """Return root, manifest, and chunk verification results without secrets."""
    repository = MetadataRepository()
    document_version = repository.get_version(document_id, version)
    if document_version is None:
        raise HTTPException(status_code=404, detail="Document version not found")
    return check_integrity(document_id, document_version, repository)


@router.post("/{document_id}/verify")
def verify_document(
    document_id: str, version: str | None = Query(default=None)
) -> dict:
    """Run integrity verification for every active chunk of one document."""
    repository = MetadataRepository()
    document_version = repository.get_version(document_id, version)
    if document_version is None:
        raise HTTPException(status_code=404, detail="Document version not found")
    return check_integrity(document_id, document_version, repository)


def check_integrity(
    document_id: str, version: dict, repository: MetadataRepository
) -> dict:
    """Verify manifest trust, stored chunk hashes, and Merkle proofs."""
    try:
        trusted_root = load_trusted_document_root(document_id, version["version"])
        manifest_valid = True
    except RuntimeError as error:
        trusted_root = ""
        manifest_valid = False
        manifest_message = str(error)
    except ValueError:
        trusted_root = ""
        manifest_valid = False
        manifest_message = "Tampered or unverified context"

    chunks = repository.get_version_chunks(document_id, version["version"])
    hash_valid = bool(chunks)
    proof_valid = bool(chunks)
    for chunk in chunks:
        stored_chunk = repository.get_chunk(chunk.chunk_id)
        if (
            stored_chunk is None
            or stored_chunk != chunk
            or not verify_chunk_hash(stored_chunk, stored_chunk.content_hash)
        ):
            hash_valid = False
        if (
            not manifest_valid
            or trusted_root != version["merkle_root"]
            or not verify_merkle_proof(chunk.content_hash, chunk.proof, trusted_root)
        ):
            proof_valid = False

    root_valid = manifest_valid and trusted_root == version["merkle_root"]
    integrity_valid = root_valid and hash_valid and proof_valid
    if not manifest_valid:
        message = manifest_message
    elif not integrity_valid:
        message = "Tampered or unverified context"
    else:
        message = "Integrity checks complete"

    return {
        "document_id": document_id,
        "version": version["version"],
        "merkle_root": version["merkle_root"],
        "active_version": bool(version["active"] and version["document_active"]),
        "manifest_valid": root_valid,
        "hashes_valid": hash_valid,
        "proofs_valid": proof_valid,
        "integrity_valid": integrity_valid,
        "message": message,
        "chunk_count": len(chunks),
    }
