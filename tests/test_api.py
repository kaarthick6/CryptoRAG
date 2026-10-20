"""Lightweight API tests that do not contact Groq or Milvus."""

from fastapi.testclient import TestClient


def get_test_client():
    """Import the app after test environment variables have been configured."""
    from app.main import app

    return TestClient(app)


def test_health_endpoint_returns_safe_dependency_status():
    response = get_test_client().get("/health")

    assert response.status_code == 200
    assert "groq_api_key_configured" in response.json()["dependencies"]
    assert "test-secret-key-that-is-at-least-32-bytes" not in response.text


def test_invalid_upload_is_rejected_before_ingestion():
    response = get_test_client().post(
        "/documents/upload",
        files={"file": ("policy.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == 400


def test_query_response_includes_source_citations(monkeypatch):
    from app.api import routes_query

    monkeypatch.setattr(
        routes_query,
        "search_and_answer",
        lambda question: {
            "answer": "Retention is seven years.",
            "sources": [
                {
                    "document": "policy.pdf",
                    "document_id": "doc-1",
                    "page_number": 4,
                    "chunk_id": "chunk-1",
                }
            ],
            "verified": True,
        },
    )
    response = get_test_client().post("/query", json={"question": "retention"})

    assert response.status_code == 200
    assert response.json()["sources"][0]["chunk_id"] == "chunk-1"


def test_query_rejects_an_empty_question():
    response = get_test_client().post("/query", json={"question": "   "})

    assert response.status_code == 422
