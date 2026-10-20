"""Sentence Transformers embeddings for document chunks and queries."""

from functools import lru_cache

from app.config import get_settings


@lru_cache(maxsize=1)
def load_embedding_model():
    """Load the configured embedding model once for this process."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise RuntimeError(
            "Install sentence-transformers to generate embeddings"
        ) from error
    try:
        return SentenceTransformer(get_settings().embedding_model)
    except Exception as error:
        raise RuntimeError("Could not load the configured embedding model") from error


def embed_chunks(texts: list[str]) -> list[list[float]]:
    """Encode document passages in batches and normalize their vectors."""
    if not texts:
        return []
    try:
        vectors = load_embedding_model().encode(
            texts, normalize_embeddings=True, convert_to_numpy=True,
            show_progress_bar=False,
        )
    except Exception as error:
        raise RuntimeError("Could not embed document chunks") from error
    return vectors.tolist()


def embed_question(question: str) -> list[float]:
    """Encode a query with the BGE query instruction used for retrieval."""
    query_text = f"Represent this sentence for searching relevant passages: {question}"
    try:
        vector = load_embedding_model().encode(
            query_text, normalize_embeddings=True, convert_to_numpy=True,
            show_progress_bar=False,
        )
    except Exception as error:
        raise RuntimeError("Could not embed the question") from error
    return vector.tolist()
