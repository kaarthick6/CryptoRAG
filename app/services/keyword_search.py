"""Persistent Whoosh BM25 index for active document chunks."""

from pathlib import Path

from whoosh import index
from whoosh.fields import ID, NUMERIC, Schema, TEXT
from whoosh.qparser import MultifieldParser, OrGroup

from app.config import get_settings


def get_schema() -> Schema:
    """Describe searchable text and stored chunk metadata."""
    return Schema(
        chunk_id=ID(stored=True, unique=True),
        document_id=ID(stored=True),
        filename=ID(stored=True),
        version=ID(stored=True),
        page_number=NUMERIC(stored=True),
        text=TEXT(stored=True),
    )


def open_index() -> index.Index:
    """Open or create the configured Whoosh index directory."""
    index_path = Path(get_settings().whoosh_index_path)
    index_path.mkdir(parents=True, exist_ok=True)
    if index.exists_in(index_path):
        return index.open_dir(index_path)
    return index.create_in(index_path, get_schema())


def index_chunks(chunks: list[dict]) -> None:
    """Replace a document's keyword entries with its current active chunks."""
    if not chunks:
        return
    try:
        writer = open_index().writer()
        document_id = chunks[0]["document_id"]
        writer.delete_by_term("document_id", document_id)
        for chunk in chunks:
            writer.add_document(**chunk)
        writer.commit()
    except Exception as error:
        raise RuntimeError("Whoosh keyword indexing failed") from error


def remove_document(document_id: str) -> None:
    """Remove all chunks belonging to a deactivated document."""
    if not Path(get_settings().whoosh_index_path).exists():
        return
    try:
        writer = open_index().writer()
        writer.delete_by_term("document_id", document_id)
        writer.commit()
    except Exception as error:
        raise RuntimeError("Whoosh keyword index cleanup failed") from error


def search_documents(question: str, limit: int | None = None) -> list[dict]:
    """Return BM25-ranked chunk references and their one-based ranks."""
    index_path = Path(get_settings().whoosh_index_path)
    if not index.exists_in(index_path):
        return []

    search_limit = limit or get_settings().retrieval_top_k
    try:
        search_index = open_index()
        parser = MultifieldParser(
            ["text"], schema=search_index.schema, group=OrGroup
        )
        query = parser.parse(question)
        with search_index.searcher() as searcher:
            results = searcher.search(query, limit=search_limit)
            return [
                {
                    "chunk_id": result["chunk_id"],
                    "document_id": result["document_id"],
                    "page_number": result["page_number"],
                    "rank": rank,
                }
                for rank, result in enumerate(results, start=1)
            ]
    except Exception as error:
        raise RuntimeError("Whoosh keyword search failed") from error
