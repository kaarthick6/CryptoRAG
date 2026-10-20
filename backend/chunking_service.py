"""Compatibility import for the active sentence-aware chunking service."""

from app.services.chunking_service import create_chunks

__all__ = ["create_chunks"]
