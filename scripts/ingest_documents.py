"""Command-line entry point for ingesting PDFs from the configured folder."""

from app.services.ingestion_service import ingest_folder


def main() -> None:
    """Run folder ingestion and print concise document results."""
    for result in ingest_folder():
        status = "unchanged" if result.unchanged else "ingested"
        print(
            f"{status}: {result.filename} | {result.chunk_count} chunks | "
            f"version {result.version[:12]} | root {result.merkle_root}"
        )


if __name__ == "__main__":
    main()
