"""Tests for hybrid result fusion and keyword ranking."""

from types import SimpleNamespace

from app.services.keyword_search import index_chunks, remove_document, search_documents
from app.services.reranking_service import rerank_chunks
from app.services.retrieval_service import combine_results


def test_rrf_merges_and_deduplicates_search_results():
    keyword_results = [
        {"chunk_id": "a", "document_id": "doc", "page_number": 1, "rank": 1},
        {"chunk_id": "b", "document_id": "doc", "page_number": 2, "rank": 2},
    ]
    semantic_results = [
        {"chunk_id": "b", "document_id": "doc", "page_number": 2, "rank": 1},
        {"chunk_id": "c", "document_id": "doc", "page_number": 3, "rank": 2},
    ]

    results = combine_results(keyword_results, semantic_results)

    assert [result["chunk_id"] for result in results] == ["b", "a", "c"]
    assert results[0]["keyword_rank"] == 2
    assert results[0]["semantic_rank"] == 1


def test_keyword_index_searches_active_document_chunks():
    index_chunks(
        [
            {
                "chunk_id": "chunk-a",
                "document_id": "doc-a",
                "filename": "policy.pdf",
                "version": "v1",
                "page_number": 5,
                "text": "Records must be retained for seven years.",
            }
        ]
    )

    results = search_documents("records retained seven years")

    assert results[0]["chunk_id"] == "chunk-a"
    assert results[0]["page_number"] == 5


def test_removed_document_is_not_returned_by_keyword_search():
    index_chunks(
        [
            {
                "chunk_id": "chunk-a",
                "document_id": "doc-a",
                "filename": "policy.pdf",
                "version": "v1",
                "page_number": 5,
                "text": "Retention policy records must be kept.",
            }
        ]
    )
    remove_document("doc-a")

    assert search_documents("retention policy") == []


def test_cross_encoder_scores_reorder_candidate_chunks(monkeypatch):
    class FakeReranker:
        def predict(self, pairs, show_progress_bar=False):
            return [0.1, 0.9]

    candidates = [
        {"chunk": SimpleNamespace(text="less relevant")},
        {"chunk": SimpleNamespace(text="more relevant")},
    ]
    monkeypatch.setattr(
        "app.services.reranking_service.load_reranker", lambda: FakeReranker()
    )

    results = rerank_chunks("question", candidates)

    assert results[0]["chunk"].text == "more relevant"
