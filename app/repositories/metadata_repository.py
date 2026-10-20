"""SQLite storage for documents, versions, chunks, hashes, and proofs."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.config import get_settings
from app.models.chunk import Chunk


class MetadataRepository:
    """Small repository that keeps all trusted document metadata in SQLite."""

    def __init__(self, database_path: Path | None = None):
        self.database_path = database_path or get_settings().sqlite_database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_tables()

    def connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with rows accessible by column name."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Close each SQLite connection after its operation is complete."""
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize_tables(self) -> None:
        """Create the document, version, and chunk tables when needed."""
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    active_version TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS document_versions (
                    document_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    merkle_root TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    active INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (document_id, version)
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    proof_json TEXT NOT NULL,
                    active INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS chunks_document_version
                ON chunks(document_id, version, active);
                """
            )

    def save_document_version(
        self, document_id: str, filename: str, version: str,
        merkle_root: str, chunks: list[Chunk],
    ) -> None:
        """Save one version and all its chunks in a single transaction."""
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.connection() as connection:
            connection.execute(
                "UPDATE document_versions SET active = 0 WHERE document_id = ?",
                (document_id,),
            )
            connection.execute(
                "UPDATE chunks SET active = 0 WHERE document_id = ?", (document_id,)
            )
            connection.execute(
                """INSERT INTO documents
                   (document_id, filename, active_version, active, updated_at)
                   VALUES (?, ?, ?, 1, ?)
                   ON CONFLICT(document_id) DO UPDATE SET
                   filename=excluded.filename, active_version=excluded.active_version,
                   active=1, updated_at=excluded.updated_at""",
                (document_id, filename, version, timestamp),
            )
            connection.execute(
                """INSERT OR REPLACE INTO document_versions
                   (document_id, version, merkle_root, chunk_count, active, created_at)
                   VALUES (?, ?, ?, ?, 1, ?)""",
                (document_id, version, merkle_root, len(chunks), timestamp),
            )
            for chunk in chunks:
                connection.execute(
                    """INSERT OR REPLACE INTO chunks
                       (chunk_id, document_id, version, filename, page_number, text,
                        content_hash, proof_json, active)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                    (
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.version,
                        chunk.filename,
                        chunk.page_number, chunk.text, chunk.content_hash,
                        json.dumps(chunk.proof, sort_keys=True),
                    ),
                )

    def list_documents(self, active_only: bool = True) -> list[dict]:
        """Return document metadata, optionally excluding deactivated documents."""
        query = """SELECT d.document_id, d.filename, d.active, v.version,
                   v.merkle_root, v.chunk_count, v.created_at
                   FROM documents d LEFT JOIN document_versions v
                   ON d.document_id = v.document_id AND d.active_version = v.version"""
        if active_only:
            query += " WHERE d.active = 1"
        query += " ORDER BY d.filename"
        with self.connection() as connection:
            return [dict(row) for row in connection.execute(query).fetchall()]

    def get_document(self, document_id: str) -> dict | None:
        """Read one document and its active version."""
        documents = self.list_documents(active_only=False)
        for document in documents:
            if document["document_id"] == document_id:
                document["versions"] = self.list_versions(document_id)
                return document
        return None

    def list_versions(self, document_id: str) -> list[dict]:
        """Return all stored versions, marking the current active version."""
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT version, merkle_root, chunk_count, active, created_at
                   FROM document_versions WHERE document_id = ?
                   ORDER BY created_at DESC""",
                (document_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_version(self, document_id: str, version: str | None = None) -> dict | None:
        """Read the active version or a specifically requested version."""
        with self.connection() as connection:
            if version is None:
                row = connection.execute(
                    """SELECT v.*, d.active AS document_active
                       FROM document_versions v JOIN documents d
                       ON d.document_id = v.document_id
                       WHERE v.document_id = ? AND v.active = 1""",
                    (document_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    """SELECT v.*, d.active AS document_active
                       FROM document_versions v JOIN documents d
                       ON d.document_id = v.document_id
                       WHERE v.document_id = ? AND v.version = ?""",
                    (document_id, version),
                ).fetchone()
        return dict(row) if row else None

    def get_chunk(self, chunk_id: str, active_only: bool = True) -> Chunk | None:
        """Load a chunk and its stored proof by stable chunk ID."""
        query = "SELECT * FROM chunks WHERE chunk_id = ?"
        if active_only:
            query += " AND active = 1"
        with self.connection() as connection:
            row = connection.execute(query, (chunk_id,)).fetchone()
        if row is None:
            return None
        return Chunk(
            chunk_id=row["chunk_id"], document_id=row["document_id"],
            filename=row["filename"], version=row["version"],
            page_number=row["page_number"], text=row["text"],
            content_hash=row["content_hash"], proof=json.loads(row["proof_json"]),
        )

    def save_merkle_data(
        self, document_id: str, version: str, merkle_root: str
    ) -> None:
        """Save a Merkle root for an already registered document version."""
        with self.connection() as connection:
            connection.execute(
                """UPDATE document_versions SET merkle_root = ?
                   WHERE document_id = ? AND version = ?""",
                (merkle_root, document_id, version),
            )

    def load_merkle_proof(
        self, document_id: str, version: str, chunk_id: str
    ) -> list[dict] | None:
        """Read a chunk's saved proof for the requested document version."""
        chunk = self.get_chunk(chunk_id, active_only=False)
        if (
            chunk is None
            or chunk.document_id != document_id
            or chunk.version != version
        ):
            return None
        return chunk.proof

    def get_active_chunks(self, document_id: str | None = None) -> list[Chunk]:
        """Read active chunks for search indexing or document verification."""
        query = "SELECT chunk_id FROM chunks WHERE active = 1"
        parameters: tuple = ()
        if document_id:
            query += " AND document_id = ?"
            parameters = (document_id,)
        with self.connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        active_chunks = []
        for row in rows:
            chunk = self.get_chunk(row["chunk_id"])
            if chunk is not None:
                active_chunks.append(chunk)
        return active_chunks

    def get_version_chunks(self, document_id: str, version: str) -> list[Chunk]:
        """Read all chunks from one version for its integrity report."""
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT chunk_id FROM chunks
                   WHERE document_id = ? AND version = ?""",
                (document_id, version),
            ).fetchall()
        chunks = []
        for row in rows:
            chunk = self.get_chunk(row["chunk_id"], active_only=False)
            if chunk is not None:
                chunks.append(chunk)
        return chunks

    def deactivate_document(self, document_id: str) -> bool:
        """Deactivate a document and its chunks so they cannot be retrieved."""
        with self.connection() as connection:
            result = connection.execute(
                "UPDATE documents SET active = 0 WHERE document_id = ?",
                (document_id,),
            )
            connection.execute(
                "UPDATE chunks SET active = 0 WHERE document_id = ?", (document_id,)
            )
            connection.execute(
                "UPDATE document_versions SET active = 0 WHERE document_id = ?",
                (document_id,),
            )
        return result.rowcount > 0
