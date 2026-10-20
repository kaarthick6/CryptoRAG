"""Milvus vector collection creation, persistence, search, and deletion."""

from functools import lru_cache

from app.config import get_settings


@lru_cache(maxsize=1)
def get_milvus_client():
    """Connect to the configured Milvus server or compatible Lite file."""
    try:
        from pymilvus import MilvusClient
    except ImportError as error:
        raise RuntimeError("Install pymilvus to use semantic search") from error

    settings = get_settings()
    try:
        client_options = {"uri": settings.milvus_uri}
        if settings.milvus_token:
            client_options["token"] = settings.milvus_token
        return MilvusClient(timeout=2, **client_options)
    except Exception as error:
        raise RuntimeError(
            "Could not connect to the configured Milvus service"
        ) from error


def ensure_collection(vector_dimension: int) -> None:
    """Create the collection and cosine index when they do not exist."""
    from pymilvus import DataType

    client = get_milvus_client()
    collection_name = get_settings().milvus_collection
    try:
        if client.has_collection(collection_name):
            description = client.describe_collection(collection_name)
            vector_field = next(
                field for field in description["fields"]
                if field["name"] == "embedding"
            )
            stored_dimension = int(vector_field["params"]["dim"])
            if stored_dimension != vector_dimension:
                raise RuntimeError(
                    "Milvus collection dimension does not match the embedding model"
                )
            return
    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError("Could not inspect the Milvus collection") from error

    schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("chunk_id", DataType.VARCHAR, is_primary=True, max_length=128)
    schema.add_field("document_id", DataType.VARCHAR, max_length=128)
    schema.add_field("filename", DataType.VARCHAR, max_length=512)
    schema.add_field("version", DataType.VARCHAR, max_length=128)
    schema.add_field("page_number", DataType.INT64)
    schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=vector_dimension)
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="embedding", index_type="AUTOINDEX", metric_type="COSINE"
    )
    try:
        client.create_collection(
            collection_name=collection_name, schema=schema, index_params=index_params
        )
    except Exception as error:
        raise RuntimeError("Could not create the Milvus vector collection") from error


def index_vectors(chunks: list[dict], vectors: list[list[float]]) -> None:
    """Persist vectors and their filterable source metadata in Milvus."""
    if not chunks:
        return
    ensure_collection(len(vectors[0]))
    entities = []
    for chunk, vector in zip(chunks, vectors):
        entities.append(
            {
                "chunk_id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
                "filename": chunk["filename"],
                "version": chunk["version"],
                "page_number": chunk["page_number"],
                "embedding": vector,
            }
        )
    try:
        get_milvus_client().upsert(
            collection_name=get_settings().milvus_collection, data=entities
        )
    except Exception as error:
        raise RuntimeError("Milvus vector indexing failed") from error


def remove_document_vectors(document_id: str) -> None:
    """Delete indexed vectors for a deactivated document."""
    client = get_milvus_client()
    collection_name = get_settings().milvus_collection
    try:
        if client.has_collection(collection_name):
            client.delete(
                collection_name=collection_name,
                filter=f'document_id == "{document_id}"',
            )
    except Exception as error:
        raise RuntimeError("Milvus vector cleanup failed") from error


def search_vectors(vector: list[float], limit: int | None = None) -> list[dict]:
    """Return semantic search hits with one-based ranks and source metadata."""
    client = get_milvus_client()
    collection_name = get_settings().milvus_collection
    try:
        if not client.has_collection(collection_name):
            return []
        search_results = client.search(
            collection_name=collection_name,
            data=[vector],
            anns_field="embedding",
            limit=limit or get_settings().retrieval_top_k,
            output_fields=["chunk_id", "document_id", "page_number", "version"],
            search_params={"metric_type": "COSINE", "params": {}},
        )
    except Exception as error:
        raise RuntimeError("Milvus semantic search failed") from error
    results = []
    for rank, hit in enumerate(search_results[0], start=1):
        entity = hit["entity"]
        results.append(
            {
                "chunk_id": entity["chunk_id"],
                "document_id": entity["document_id"],
                "page_number": entity["page_number"],
                "version": entity["version"],
                "rank": rank,
            }
        )
    return results
