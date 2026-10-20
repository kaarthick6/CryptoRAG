"""HTTP client for the FastAPI backend."""

import os

import requests
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("FRONTEND_API_URL", "http://127.0.0.1:8000")


def get_health() -> dict:
    """Read service status and safe dependency information."""
    return request("GET", "/health")


def get_documents() -> list[dict]:
    """List active documents and their current versions."""
    return request("GET", "/documents")


def get_document(document_id: str) -> dict:
    """Read metadata and version history for one document."""
    return request("GET", f"/documents/{document_id}")


def ingest_folder() -> dict:
    """Ask the backend to ingest PDFs from its configured folder."""
    return request("POST", "/documents/ingest-folder")


def upload_pdf(filename: str, file_bytes: bytes) -> dict:
    """Upload and ingest one PDF without sending secrets to the frontend."""
    files = {"file": (filename, file_bytes, "application/pdf")}
    response = requests.post(f"{API_URL}/documents/upload", files=files, timeout=600)
    return parse_response(response)


def ask_question(question: str) -> dict:
    """Submit a question to the verified backend query pipeline."""
    return request("POST", "/query", json={"question": question}, timeout=300)


def get_integrity(document_id: str, version: str | None = None) -> dict:
    """Read integrity information for the selected document."""
    return request(
        "GET", f"/documents/{document_id}/integrity", params={"version": version}
    )


def verify_document(document_id: str, version: str | None = None) -> dict:
    """Run all active chunk checks for the selected document."""
    return request(
        "POST", f"/documents/{document_id}/verify", params={"version": version}
    )


def delete_document(document_id: str) -> dict:
    """Deactivate a document through the backend."""
    return request("DELETE", f"/documents/{document_id}")


def request(method: str, path: str, **options) -> dict | list:
    """Send a request and raise a readable message for backend failures."""
    response = requests.request(method, f"{API_URL}{path}", timeout=30, **options)
    return parse_response(response)


def parse_response(response):
    """Decode JSON and include the backend's safe error detail on failure."""
    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        try:
            detail = response.json().get("detail", str(error))
        except ValueError:
            detail = str(error)
        raise RuntimeError(str(detail)) from error
    return response.json()
