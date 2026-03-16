"""E2E: ingest docs → FTS search returns correct results."""

from __future__ import annotations

import pytest

from docflow.db import Database


@pytest.mark.e2e
class TestE2EFullTextSearch:
    def _insert_doc(
        self,
        db: Database,
        run_id: int,
        ocr_text: str,
        doc_type: str,
        tags: list[str],
        filename: str,
    ):
        return db.insert_document(
            run_id=run_id,
            original_photo_id=f"uid-{filename}",
            original_filename=f"{filename}.jpg",
            ocr_text=ocr_text,
            llm_provider="anthropic",
            doc_type=doc_type,
            tags=tags,
            suggested_filename=f"{filename}.pdf",
            saved_path=f"/tmp/{filename}.pdf",
        )

    def test_fts_finds_ocr_text(self, e2e_db: Database):
        run_id = e2e_db.create_run()
        self._insert_doc(
            e2e_db, run_id, "Rechnung Vodafone GmbH 45 EUR", "Rechnung", ["Vodafone"], "vodafone"
        )
        self._insert_doc(
            e2e_db,
            run_id,
            "Kontoauszug Deutsche Bank Januar",
            "Kontoauszug",
            ["DeutscheBank"],
            "bank",
        )
        self._insert_doc(
            e2e_db, run_id, "Mietvertrag Berlin Kreuzberg", "Vertrag", ["Miete"], "miete"
        )

        results = e2e_db.search_documents("Vodafone")
        assert len(results) == 1
        assert results[0]["doc_type"] == "Rechnung"

    def test_fts_finds_doc_type(self, e2e_db: Database):
        run_id = e2e_db.create_run()
        self._insert_doc(e2e_db, run_id, "text A", "Rechnung", [], "r1")
        self._insert_doc(e2e_db, run_id, "text B", "Kontoauszug", [], "k1")

        results = e2e_db.search_documents("Kontoauszug")
        assert any(d["doc_type"] == "Kontoauszug" for d in results)

    def test_fts_finds_tag(self, e2e_db: Database):
        run_id = e2e_db.create_run()
        self._insert_doc(e2e_db, run_id, "something", "Brief", ["Telekom", "2026-03"], "brief")
        self._insert_doc(e2e_db, run_id, "something else", "Rechnung", ["Amazon"], "amz")

        results = e2e_db.search_documents("Telekom")
        assert len(results) == 1
        assert results[0]["doc_type"] == "Brief"

    def test_fts_finds_filename(self, e2e_db: Database):
        run_id = e2e_db.create_run()
        self._insert_doc(e2e_db, run_id, "other", "Brief", [], "2026-03_GEZ_Bescheid")

        results = e2e_db.search_documents("GEZ")
        assert len(results) == 1

    def test_fts_no_results_for_unknown_term(self, e2e_db: Database):
        run_id = e2e_db.create_run()
        self._insert_doc(e2e_db, run_id, "Rechnung Vodafone", "Rechnung", [], "v1")

        results = e2e_db.search_documents("XYZNonExistentTerm12345")
        assert len(results) == 0

    def test_fts_case_insensitive(self, e2e_db: Database):
        run_id = e2e_db.create_run()
        self._insert_doc(e2e_db, run_id, "Rechnung VODAFONE GmbH", "Rechnung", [], "v2")

        # FTS5 is case-insensitive by default for ASCII
        results = e2e_db.search_documents("vodafone")
        assert len(results) == 1

    def test_fts_multiple_results(self, e2e_db: Database):
        run_id = e2e_db.create_run()
        for i in range(5):
            self._insert_doc(
                e2e_db,
                run_id,
                f"Rechnung Amazon Bestellung {i}",
                "Rechnung",
                ["Amazon"],
                f"amz_{i}",
            )
        self._insert_doc(e2e_db, run_id, "Kontoauszug DKB", "Kontoauszug", [], "dkb")

        results = e2e_db.search_documents("Amazon")
        assert len(results) == 5

    def test_list_documents_filter_after_fts_insert(self, e2e_db: Database):
        """Regular listing still works after FTS inserts."""
        run_id = e2e_db.create_run()
        self._insert_doc(e2e_db, run_id, "text", "Rechnung", [], "r1")
        self._insert_doc(e2e_db, run_id, "text", "Vertrag", [], "v1")

        all_docs = e2e_db.list_documents()
        assert len(all_docs) == 2

        rechnungen = e2e_db.list_documents(doc_type="Rechnung")
        assert len(rechnungen) == 1
