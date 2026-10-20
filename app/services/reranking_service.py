"""Rerank hybrid retrieval results with a Sentence Transformers cross-encoder."""

from functools import lru_cache

from app.config import get_settings


@lru_cache(maxsize=1)
def load_reranker():
    """Load the configured cross-encoder once for this application process."""
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as error:
        raise RuntimeError("Install sentence-transformers to rerank results") from error
    try:
        return CrossEncoder(get_settings().reranker_model)
    except Exception as error:
        raise RuntimeError("Could not load the configured reranker model") from error


def rerank_chunks(question: str, candidates: list[dict]) -> list[dict]:
    """Score question and chunk pairs, returning the highest scores first."""
    if not candidates:
        return []
    pairs = [(question, result["chunk"].text) for result in candidates]
    try:
        scores = load_reranker().predict(pairs, show_progress_bar=False)
    except Exception as error:
        raise RuntimeError("Could not rerank retrieved chunks") from error
    ranked_candidates = []
    for candidate, score in zip(candidates, scores):
        ranked_candidates.append({**candidate, "reranker_score": float(score)})
    return sorted(
        ranked_candidates, key=lambda item: item["reranker_score"], reverse=True
    )
