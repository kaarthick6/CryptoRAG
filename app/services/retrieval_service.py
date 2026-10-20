"""Hybrid retrieval, rank fusion, reranking, and evidence generation flow."""

from app.config import get_settings
from app.repositories.metadata_repository import MetadataRepository
from app.services.embedding_service import embed_question
from app.services.generation_service import generate_answer
from app.services.keyword_search import search_documents
from app.services.reranking_service import rerank_chunks
from app.services.vector_search import search_vectors
from app.services.verification_service import verify_chunks


def combine_results(
    keyword_results: list[dict], semantic_results: list[dict]
) -> list[dict]:
    """Combine independent result lists with RRF and deduplicate chunk IDs."""
    reciprocal_rank_k = get_settings().rrf_k
    combined = {}
    for source_name, results in (
        ("keyword_rank", keyword_results),
        ("semantic_rank", semantic_results),
    ):
        for result in results:
            chunk_id = result["chunk_id"]
            if chunk_id not in combined:
                combined[chunk_id] = {
                    "chunk_id": chunk_id,
                    "document_id": result["document_id"],
                    "page_number": result["page_number"],
                    "rrf_score": 0.0,
                    "keyword_rank": None,
                    "semantic_rank": None,
                }
            combined[chunk_id]["rrf_score"] += 1 / (
                reciprocal_rank_k + result["rank"]
            )
            combined[chunk_id][source_name] = result["rank"]
    return sorted(combined.values(), key=lambda item: item["rrf_score"], reverse=True)


def retrieve_candidates(question: str) -> list[dict]:
    """Search both indexes, fuse ranks, and load active chunk text from SQLite."""
    query_vector = embed_question(question)
    keyword_results = search_documents(question)
    semantic_results = search_vectors(query_vector)
    fused_results = combine_results(keyword_results, semantic_results)
    repository = MetadataRepository()
    candidates = []

    for result in fused_results[: get_settings().retrieval_top_k]:
        chunk = repository.get_chunk(result["chunk_id"])
        if chunk is None:
            continue
        candidates.append({**result, "chunk": chunk})
    return candidates


def search_and_answer(question: str, generator=generate_answer) -> dict:
    """Retrieve, rerank, verify, then generate from verified context only."""
    candidates = retrieve_candidates(question)
    if not candidates:
        return {
            "answer": "I could not find sufficient evidence in the indexed documents.",
            "sources": [],
            "verified": False,
        }

    reranked_candidates = rerank_chunks(question, candidates)
    selected_chunks = [
        item["chunk"] for item in reranked_candidates[: get_settings().rerank_top_k]
    ]
    verified_context = verify_chunks(selected_chunks)
    answer = generator(question, verified_context)
    citations = [
        {
            "document": chunk.filename,
            "document_id": chunk.document_id,
            "page_number": chunk.page_number,
            "chunk_id": chunk.chunk_id,
        }
        for chunk in verified_context
    ]
    return {"answer": answer, "sources": citations, "verified": True}
