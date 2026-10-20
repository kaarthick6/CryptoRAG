"""Validated settings shared by the backend services."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    frontend_api_url: str = "http://127.0.0.1:8000"
    compliance_documents_path: Path = Path("./data/compliance-documents")
    sqlite_database_path: Path = Path("./storage/app.db")
    whoosh_index_path: Path = Path("./storage/whoosh_index")
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str | None = None
    milvus_collection: str = "compliance_chunks"
    embedding_model: str = "BAAI/bge-large-en"
    reranker_model: str = "BAAI/bge-reranker-base"
    llm_provider: str = "groq"
    llm_model: str = "llama-3.1-8b-instant"
    groq_api_key: str | None = None
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1024
    manifest_path: Path = Path("./storage/trusted_manifest.json")
    manifest_signing_key: str | None = Field(default=None, repr=False)
    chunk_size: int = 800
    chunk_overlap: int = 120
    retrieval_top_k: int = 20
    rerank_top_k: int = 5
    rrf_k: int = 60
    max_upload_size_mb: int = 25


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one settings object for this application process."""
    return Settings()
