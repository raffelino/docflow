"""Unit tests for the database layer."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from docflow.db import Database


@pytest.mark.unit
class TestDatabase:
    def test_create_and_finish_run(self, db: Database):
        run_id = db.create_run()
        assert isinstance(run_id, int)
        assert run_id > 0

        run = db.get_run(run_id)
        assert run is not None
        assert run["status"] == "running"

        db.finish_run(
            run_id=run_id,
            status="success",
            photos_found=3,
            docs_processed=3,
            errors=0,
            log="all good",
        )
        run = db.get_run(run_id)
        assert run["status"] == "success"
        assert run["photos_found"] == 3
        assert run["docs_processed"] == 3
        assert run["errors"] == 0
        assert run["log"] == "all good"
        assert run["finished_at"] is not None

    def test_list_runs_order(self, db: Database):
        ids = [db.create_run() for _ in range(5)]
        runs = db.list_runs(limit=10)
        assert len(runs) == 5
        # Most recent first
        assert runs[0]["id"] == max(ids)

    def test_list_runs_limit(self, db: Database):
        for _ in range(8):
            db.create_run()
        runs = db.list_runs(limit=3)
        assert len(runs) == 3

    def test_insert_and_get_document(self, db: Database):
        run_id = db.create_run()
        doc_id = db.insert_document(
            run_id=run_id,
            original_photo_id="uuid-001",
            original_filename="scan.jpg",
            ocr_text="Rechnung von Vodafone 45 EUR",
            llm_provider="anthropic",
            doc_type="Rechnung",
            tags=["Vodafone", "2026-03"],
            suggested_filename="2026-03_Vodafone_Rechnung.pdf",
            saved_path="/tmp/2026/03/2026-03_Vodafone_Rechnung.pdf",
        )
        assert doc_id > 0

        doc = db.get_document(doc_id)
        assert doc is not None
        assert doc["doc_type"] == "Rechnung"
        assert doc["suggested_filename"] == "2026-03_Vodafone_Rechnung.pdf"
        tags = json.loads(doc["tags"])
        assert "Vodafone" in tags

    def test_insert_document_with_email_fields(self, db: Database):
        run_id = db.create_run()
        doc_id = db.insert_document(
            run_id=run_id,
            original_photo_id="email-uid-001",
            original_filename="invoice.pdf",
            ocr_text="Invoice from Amazon",
            llm_provider="ollama",
            doc_type="Rechnung",
            tags=["Amazon"],
            suggested_filename="2026-03_Amazon_Rechnung.pdf",
            saved_path="/tmp/invoice.pdf",
            source="email",
            email_subject="Your Amazon Order",
            email_sender="no-reply@amazon.de",
            email_date=datetime(2026, 3, 10, 9, 0),
        )
        doc = db.get_document(doc_id)
        assert doc["source"] == "email"
        assert doc["email_subject"] == "Your Amazon Order"
        assert doc["email_sender"] == "no-reply@amazon.de"

    def test_list_documents_filter_by_type(self, db: Database):
        run_id = db.create_run()
        for doc_type in ["Rechnung", "Rechnung", "Kontoauszug"]:
            db.insert_document(
                run_id=run_id,
                original_photo_id="x",
                original_filename="x.jpg",
                ocr_text="text",
                llm_provider="anthropic",
                doc_type=doc_type,
                tags=[],
                suggested_filename="x.pdf",
                saved_path="/tmp/x.pdf",
            )

        rechnungen = db.list_documents(doc_type="Rechnung")
        assert len(rechnungen) == 2
        kontoauszuege = db.list_documents(doc_type="Kontoauszug")
        assert len(kontoauszuege) == 1

    def test_list_documents_filter_by_source(self, db: Database):
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
        photos_docs = db.list_documents(source="photos")
        assert all(d["source"] == "photos" for d in photos_docs)
        email_docs = db.list_documents(source="email")
        assert all(d["source"] == "email" for d in email_docs)

    def test_fts_search(self, db: Database):
        run_id = db.create_run()
        db.insert_document(
            run_id=run_id,
            original_photo_id="uuid-fts",
            original_filename="vodafone.jpg",
            ocr_text="Rechnung Vodafone GmbH Betrag: 45,00 EUR",
            llm_provider="anthropic",
            doc_type="Rechnung",
            tags=["Vodafone", "Telekommunikation"],
            suggested_filename="2026-03_Vodafone_Rechnung.pdf",
            saved_path="/tmp/vodafone.pdf",
        )
        db.insert_document(
            run_id=run_id,
            original_photo_id="uuid-fts2",
            original_filename="amazon.jpg",
            ocr_text="Amazon Bestellung Lieferschein",
            llm_provider="anthropic",
            doc_type="Lieferschein",
            tags=["Amazon"],
            suggested_filename="2026-03_Amazon_Lieferschein.pdf",
            saved_path="/tmp/amazon.pdf",
        )

        results = db.search_documents("Vodafone")
        assert len(results) == 1
        assert results[0]["doc_type"] == "Rechnung"

        results2 = db.search_documents("Amazon")
        assert len(results2) == 1
        assert results2[0]["doc_type"] == "Lieferschein"

    def test_list_doc_types(self, db: Database):
        run_id = db.create_run()
        for dt in ["Rechnung", "Vertrag", "Rechnung"]:
            db.insert_document(
                run_id=run_id,
                original_photo_id="x",
                original_filename="x.jpg",
                ocr_text="t",
                llm_provider="a",
                doc_type=dt,
                tags=[],
                suggested_filename="x.pdf",
                saved_path="/tmp/x.pdf",
            )
        types = db.list_doc_types()
        assert "Rechnung" in types
        assert "Vertrag" in types
        assert len(set(types)) == len(types)  # no duplicates

    def test_migration_idempotent(self, tmp_dir: Path):
        """Opening a DB twice should not fail (migration triggers are safe)."""
        Database(tmp_dir / "idempotent.db")
        db2 = Database(tmp_dir / "idempotent.db")
        run_id = db2.create_run()
        assert run_id == 1
