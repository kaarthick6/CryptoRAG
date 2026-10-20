"""FastAPI application entry point and health route."""

import logging
import sqlite3

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes_documents import router as documents_router
from app.api.routes_query import router as query_router
from app.config import get_settings
from app.repositories.metadata_repository import MetadataRepository
from app.services.vector_search import get_milvus_client
from app.utils.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()
settings.compliance_documents_path.mkdir(parents=True, exist_ok=True)
settings.sqlite_database_path.parent.mkdir(parents=True, exist_ok=True)
MetadataRepository()

app = FastAPI(title="Cryptography-Anchored RAG Compliance System")
app.include_router(documents_router)
app.include_router(query_router)


@app.exception_handler(sqlite3.Error)
def sqlite_error_handler(request, error: sqlite3.Error) -> JSONResponse:
    """Return a clear storage failure without exposing SQL or document data."""
    logger.exception("SQLite metadata operation failed")
    return JSONResponse(
        status_code=503,
        content={"detail": "SQLite metadata storage is unavailable"},
    )


@app.exception_handler(Exception)
def unexpected_error_handler(request, error: Exception) -> JSONResponse:
    """Log unexpected failures safely and return a generic server response."""
    logger.exception("Unexpected application error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health_check() -> dict:
    """Return service readiness without disclosing credentials or secrets."""
    sqlite_status = "ready"
    keyword_status = (
        "ready" if settings.whoosh_index_path.exists() else "not indexed yet"
    )
    milvus_status = "not checked"
    try:
        get_milvus_client().list_collections()
        milvus_status = "connected"
    except Exception:
        milvus_status = "unavailable"

    return {
        "status": (
            "ok"
            if milvus_status == "connected"
            and settings.groq_api_key
            and settings.manifest_signing_key
            and len(settings.manifest_signing_key.encode("utf-8")) >= 32
            else "degraded"
        ),
        "dependencies": {
            "sqlite": sqlite_status,
            "whoosh": keyword_status,
            "milvus": milvus_status,
            "groq_api_key_configured": bool(settings.groq_api_key),
            "manifest_signing_key_configured": bool(
                settings.manifest_signing_key
                and len(settings.manifest_signing_key.encode("utf-8")) >= 32
            ),
            "embedding_model": settings.embedding_model,
            "reranker_model": settings.reranker_model,
        },
    }
