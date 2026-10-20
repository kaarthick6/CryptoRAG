"""Temporary application settings for isolated service tests."""

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def temporary_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("SQLITE_DATABASE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("WHOOSH_INDEX_PATH", str(tmp_path / "whoosh"))
    monkeypatch.setenv("MANIFEST_PATH", str(tmp_path / "manifest.json"))
    signing_key = "test-secret-key-that-is-at-least-32-bytes"
    monkeypatch.setenv("MANIFEST_SIGNING_KEY", signing_key)
    monkeypatch.setenv("COMPLIANCE_DOCUMENTS_PATH", str(tmp_path / "pdfs"))
    monkeypatch.setenv("MILVUS_URI", "http://127.0.0.1:19530")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
