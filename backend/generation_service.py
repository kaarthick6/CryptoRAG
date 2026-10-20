"""Compatibility import for verified-context Groq generation."""

from app.services.generation_service import generate_answer

__all__ = ["generate_answer"]
