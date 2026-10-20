"""Tests proving that only verified context can reach generation."""

from unittest.mock import Mock

import pytest

from app.api.schemas import QueryRequest
from app.models.chunk import VerifiedChunk
from app.services import retrieval_service


def test_failed_verification_makes_zero_generation_calls(monkeypatch):
    candidate = {"chunk": object()}
    monkeypatch.setattr(
        retrieval_service, "retrieve_candidates", lambda question: [candidate]
    )
    monkeypatch.setattr(
        retrieval_service, "rerank_chunks", lambda question, items: items
    )
    monkeypatch.setattr(
        retrieval_service, "verify_chunks",
        lambda chunks: (_ for _ in ()).throw(
            ValueError("Tampered or unverified context")
        ),
    )
    generator = Mock(return_value="unsafe answer")

    with pytest.raises(ValueError, match="Tampered or unverified context"):
        retrieval_service.search_and_answer("policy question", generator=generator)

    generator.assert_not_called()


def test_no_candidates_makes_zero_generation_calls(monkeypatch):
    monkeypatch.setattr(retrieval_service, "retrieve_candidates", lambda question: [])
    generator = Mock(return_value="should not run")

    result = retrieval_service.search_and_answer("unknown", generator=generator)

    assert result["sources"] == []
    generator.assert_not_called()


def test_valid_verified_context_can_reach_generation(monkeypatch):
    chunk = VerifiedChunk("chunk", "doc", "policy.pdf", "v1", 2, "evidence")
    monkeypatch.setattr(
        retrieval_service, "retrieve_candidates", lambda question: [{"chunk": chunk}]
    )
    monkeypatch.setattr(
        retrieval_service, "rerank_chunks", lambda question, items: items
    )
    monkeypatch.setattr(retrieval_service, "verify_chunks", lambda chunks: [chunk])
    generator = Mock(return_value="answer [policy.pdf, page 2]")

    result = retrieval_service.search_and_answer("question", generator=generator)

    generator.assert_called_once_with("question", [chunk])
    assert result["verified"]
    assert result["sources"][0]["chunk_id"] == "chunk"


def test_client_cannot_pass_a_verified_bypass_flag():
    request = QueryRequest(question="question", verified=True)

    assert not hasattr(request, "verified")
