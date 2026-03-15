"""Unit tests for the FastAPI web UI."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from docflow.config import Settings
from docflow.db import Database
from docflow.web.app import create_app


def _make_app(tmp_dir: Path):
    settings = Settings(
        photos_album="TestAlbum",
        output_dir=tmp_dir / "output",
        db_path=tmp_dir / "web_test.db",
        llm_provider="anthropic",
        anthropic_api_key="test",
        storage_backend="local",
        email_enabled=False,
    )
    app = create_app(settings)
    return app, settings


@pytest.mark.unit
class TestWebRoutes:
    def test_index_returns_200(self, tmp_dir: Path):
        app, _ = _make_app(tmp_dir)
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "DocFlow" in resp.text

    def test_documents_page_returns_200(self, tmp_dir: Path):
        app, _ = _make_app(tmp_dir)
        client = TestClient(app)
        resp = client.get("/documents")
        assert resp.status_code == 200

    def test_run_detail_404_for_missing(self, tmp_dir: Path):
        app, _ = _make_app(tmp_dir)
        client = TestClient(app)
        resp = client.get("/runs/9999")
        assert resp.status_code == 404

    def test_run_detail_shows_run(self, tmp_dir: Path):
        app, settings = _make_app(tmp_dir)
        db = Database(settings.db_path)
        run_id = db.create_run()
        db.finish_run(run_id, "success", 1, 1, 0, "log line")

        client = TestClient(app)
        resp = client.get(f"/runs/{run_id}")
        assert resp.status_code == 200
        assert str(run_id) in resp.text

    def test_api_runs_returns_list(self, tmp_dir: Path):
        app, settings = _make_app(tmp_dir)
        db = Database(settings.db_path)
        db.create_run()

        client = TestClient(app)
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_api_documents_returns_list(self, tmp_dir: Path):
        app, settings = _make_app(tmp_dir)
        db = Database(settings.db_path)
        run_id = db.create_run()
        db.insert_document(
            run_id=run_id, original_photo_id="u1", original_filename="f.jpg",
            ocr_text="hello", llm_provider="a", doc_type="Brief",
            tags=["tag1"], suggested_filename="brief.pdf", saved_path="/tmp/brief.pdf",
        )

        client = TestClient(app)
        resp = client.get("/api/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["doc_type"] == "Brief"
        assert isinstance(data[0]["tags_list"], list)

    def test_api_documents_search(self, tmp_dir: Path):
        app, settings = _make_app(tmp_dir)
        db = Database(settings.db_path)
        run_id = db.create_run()
        db.insert_document(
            run_id=run_id, original_photo_id="u1", original_filename="f.jpg",
            ocr_text="Vodafone Rechnung März", llm_provider="a", doc_type="Rechnung",
            tags=["Vodafone"], suggested_filename="vodafone.pdf", saved_path="/tmp/v.pdf",
        )
        db.insert_document(
            run_id=run_id, original_photo_id="u2", original_filename="g.jpg",
            ocr_text="Amazon Lieferschein Paket", llm_provider="a", doc_type="Lieferschein",
            tags=["Amazon"], suggested_filename="amazon.pdf", saved_path="/tmp/a.pdf",
        )

        client = TestClient(app)
        resp = client.get("/api/documents?q=Vodafone")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["doc_type"] == "Rechnung"

    def test_api_document_404(self, tmp_dir: Path):
        app, _ = _make_app(tmp_dir)
        client = TestClient(app)
        resp = client.get("/api/documents/99999")
        assert resp.status_code == 404

    def test_trigger_run_redirects(self, tmp_dir: Path):
        app, _ = _make_app(tmp_dir)
        client = TestClient(app, follow_redirects=False)

        with patch("docflow.web.routes._do_run"):
            resp = client.post("/runs/trigger")
        # Should redirect to /
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"

    def test_documents_filter_by_type(self, tmp_dir: Path):
        app, settings = _make_app(tmp_dir)
        db = Database(settings.db_path)
        run_id = db.create_run()
        db.insert_document(
            run_id=run_id, original_photo_id="u1", original_filename="r.jpg",
            ocr_text="rechnung text", llm_provider="a", doc_type="Rechnung",
            tags=[], suggested_filename="r.pdf", saved_path="/tmp/r.pdf",
        )
        db.insert_document(
            run_id=run_id, original_photo_id="u2", original_filename="v.jpg",
            ocr_text="vertrag text", llm_provider="a", doc_type="Vertrag",
            tags=[], suggested_filename="v.pdf", saved_path="/tmp/v.pdf",
        )

        client = TestClient(app)
        resp = client.get("/documents?doc_type=Rechnung")
        assert resp.status_code == 200
        assert "Rechnung" in resp.text
