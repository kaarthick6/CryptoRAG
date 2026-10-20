"""Compatibility import for cross-encoder chunk reranking."""

from app.services.reranking_service import rerank_chunks

__all__ = ["rerank_chunks"]
