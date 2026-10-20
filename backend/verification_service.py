"""Compatibility imports for the active SQLite-backed verification service."""

from app.services.verification_service import verify_chunk, verify_chunks

__all__ = ["verify_chunk", "verify_chunks"]
