"""E2E: full FastAPI app — hit all routes, assert responses."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from docflow.config import Settings
from docflow.db import Database
from docflow.web.app import create_app


def _client_and_db(e2e_dir: Path) -> tuple[TestClient, Database, Settings]:
    settings = Settings(
        photos_album="E2EAlbum",
        output_dir=e2e_dir / "output",
        db_path=e2e_dir / "web_e2e.db",
        llm_provider="anthropic",
        anthropic_api_key="test",
        storage_backend="local",
        email_enabled=False,
    )
    app = create_app(settings)
    db = Database(settings.db_path)
    return TestClient(app), db, settings


@pytest.mark.e2e
class TestE2EWebApp:
    def test_dashboard_empty(self, e2e_dir: Path):
        client, db, _ = _client_and_db(e2e_dir)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "DocFlow" in resp.text
        assert "Noch keine Läufe" in resp.text

    def test_dashboard_with_runs(self, e2e_dir: Path):
        client, db, _ = _client_and_db(e2e_dir)
        run_id = db.create_run()
        db.finish_run(run_id, "success", 2, 2, 0, "log data")

        resp = client.get("/")
        assert resp.status_code == 200
        assert "success" in resp.text.lower() or "OK" in resp.text

    def test_run_detail_with_docs(self, e2e_dir: Path):
        client, db, _ = _client_and_db(e2e_dir)
        run_id = db.create_run()
        db.finish_run(run_id, "success", 1, 1, 0, "some log\nanother line")
        db.insert_document(
            run_id=run_id,
            original_photo_id="x",
            original_filename="scan.jpg",
            ocr_text="Rechnung Vodafone",
            llm_provider="anthropic",
            doc_type="Rechnung",
            tags=["Vodafone"],
            suggested_filename="2026-03_Vodafone_Rechnung.pdf",
            saved_path="/tmp/vodafone.pdf",
        )

        resp = client.get(f"/runs/{run_id}")
        assert resp.status_code == 200
        assert "Vodafone" in resp.text
        assert "some log" in resp.text

    def test_documents_empty(self, e2e_dir: Path):
        client, db, _ = _client_and_db(e2e_dir)
        resp = client.get("/documents")
        assert resp.status_code == 200
        assert "Noch keine Dokumente" in resp.text

    def test_documents_list(self, e2e_dir: Path):
        client, db, _ = _client_and_db(e2e_dir)
        run_id = db.create_run()
        db.insert_document(
            run_id=run_id,
            original_photo_id="u1",
            original_filename="a.jpg",
            ocr_text="Amazon Lieferschein",
            llm_provider="a",
            doc_type="Lieferschein",
            tags=["Amazon"],
            suggested_filename="amazon.pdf",
            saved_path="/tmp/a.pdf",
            source="email",
            email_sender="no-reply@amazon.de",
            email_subject="Ihre Bestellung",
        )

        resp = client.get("/documents")
        assert resp.status_code == 200
        assert "Lieferschein" in resp.text
        assert "Amazon" in resp.text
        # Email source icon should appear
        assert "✉" in resp.text or "E-Mail" in resp.text

    def test_documents_search(self, e2e_dir: Path):
        client, db, _ = _client_and_db(e2e_dir)
        run_id = db.create_run()
        db.insert_document(
            run_id=run_id,
            original_photo_id="u1",
            original_filename="x.jpg",
            ocr_text="Telekom Rechnung März 2026",
            llm_provider="a",
            doc_type="Rechnung",
            tags=["Telekom"],
            suggested_filename="telekom.pdf",
            saved_path="/tmp/t.pdf",
        )
        db.insert_document(
            run_id=run_id,
            original_photo_id="u2",
            original_filename="y.jpg",
            ocr_text="DKB Kontoauszug",
            llm_provider="a",
            doc_type="Kontoauszug",
            tags=["DKB"],
            suggested_filename="dkb.pdf",
            saved_path="/tmp/d.pdf",
        )

        resp = client.get("/documents?q=Telekom")
        assert resp.status_code == 200
        assert "Telekom" in resp.text
        # DKB should not appear in filtered results
        assert "DKB" not in resp.text

    def test_documents_filter_by_source(self, e2e_dir: Path):
        client, db, _ = _client_and_db(e2e_dir)
        run_id = db.create_run()
        db.insert_document(
            run_id=run_id,
            original_photo_id="p1",
            original_filename="p.jpg",
            ocr_text="photo doc",
            llm_provider="a",
            doc_type="Brief",
            tags=[],
            suggested_filename="p.pdf",
            saved_path="/tmp/p.pdf",
            source="photos",
        )
        db.insert_document(
            run_id=run_id,
            original_photo_id="e1",
            original_filename="e.pdf",
            ocr_text="email doc",
            llm_provider="a",
            doc_type="Rechnung",
            tags=[],
            suggested_filename="e.pdf",
            saved_path="/tmp/e.pdf",
            source="email",
        )

        resp = client.get("/documents?source=email")
        assert resp.status_code == 200
        # Only email doc should be visible
        assert "Rechnung" in resp.text

    def test_api_runs_json(self, e2e_dir: Path):
        client, db, _ = _client_and_db(e2e_dir)
        run_id = db.create_run()
        db.finish_run(run_id, "success", 0, 0, 0, "")

        resp = client.get("/api/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data[0]["id"] == run_id
        assert data[0]["status"] == "success"

    def test_api_documents_json(self, e2e_dir: Path):
        client, db, _ = _client_and_db(e2e_dir)
        run_id = db.create_run()
        db.insert_document(
            run_id=run_id,
            original_photo_id="u",
            original_filename="f.jpg",
            ocr_text="text",
            llm_provider="a",
            doc_type="Brief",
            tags=["tag1", "tag2"],
            suggested_filename="brief.pdf",
            saved_path="/tmp/b.pdf",
        )

        resp = client.get("/api/documents")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["doc_type"] == "Brief"
        assert "tag1" in data[0]["tags_list"]

    def test_api_document_by_id(self, e2e_dir: Path):
        client, db, _ = _client_and_db(e2e_dir)
        run_id = db.create_run()
        doc_id = db.insert_document(
            run_id=run_id,
            original_photo_id="u",
            original_filename="f.jpg",
            ocr_text="text",
            llm_provider="a",
            doc_type="Vertrag",
            tags=[],
            suggested_filename="v.pdf",
            saved_path="/tmp/v.pdf",
        )

        resp = client.get(f"/api/documents/{doc_id}")
        assert resp.status_code == 200
        assert resp.json()["doc_type"] == "Vertrag"

    def test_trigger_run_no_error(self, e2e_dir: Path):
        client, _, _ = _client_and_db(e2e_dir)

        with patch("docflow.web.routes._do_run"):
            resp = client.post("/runs/trigger", follow_redirects=False)
        assert resp.status_code == 303
