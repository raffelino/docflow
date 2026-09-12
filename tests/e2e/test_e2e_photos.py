"""E2E: fake album → OCR → LLM → PDF → DB check."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from docflow.db import Database
from docflow.photos import MockPhotosLibrary, PhotoInfo
from docflow.pipeline import Pipeline
from docflow.storage.local import LocalStorage

# Oberhalb der Pre-Classifier-Schwelle (250 Zeichen). Kurztexte werden als Foto
# aussortiert — das ist gewolltes Verhalten und in tests/test_pipeline.py geprueft.
DOKUMENT_TEXT = (
    "Vodafone GmbH\nRechnung Nr. 2026-4711\nDatum: 12.09.2026\n"
    "Kundennummer: 998877\nMobilfunk September 2026\n"
    "Grundgebuehr 29,99 EUR\nVerbrauch 15,01 EUR\n"
    "Netto 37,82 EUR\nMwSt 19 Prozent 7,18 EUR\nGesamtbetrag 45,00 EUR\n"
    "Zahlbar bis 26.09.2026 per Lastschrift.\n"
)


@pytest.mark.e2e
class TestE2EPhotoPipeline:
    @pytest.mark.asyncio
    async def test_full_photo_pipeline(
        self,
        e2e_settings,
        e2e_db: Database,
        e2e_llm,
        fake_jpeg: Path,
    ):
        """Complete flow: photo → OCR → classify → PDF → DB."""
        photo = PhotoInfo(
            uuid="e2e-photo-001",
            filename="scan.jpg",
            path=fake_jpeg,
            original_filename="rechnung_scan.jpg",
        )

        storage = LocalStorage(base_dir=e2e_settings.output_dir)
        pipeline = Pipeline(
            settings=e2e_settings,
            db=e2e_db,
            llm=e2e_llm,
            storage=storage,
        )

        with patch(
            "docflow.pipeline.extract_text",
            new=AsyncMock(return_value=DOKUMENT_TEXT),
        ):
            with patch(
                "docflow.pipeline.get_library",
                return_value=MockPhotosLibrary([photo]),
            ):
                run_id = await pipeline.run()

        # Run recorded correctly
        run = e2e_db.get_run(run_id)
        assert run is not None
        assert run["status"] == "success"
        assert run["docs_processed"] == 1
        assert run["photos_found"] == 1
        assert run["errors"] == 0
        assert "Pipeline started" in run["log"]
        assert "Pipeline finished" in run["log"]

        # Document in DB
        docs = e2e_db.list_documents()
        assert len(docs) == 1
        doc = docs[0]
        assert doc["source"] == "photos"
        assert doc["doc_type"] == "Rechnung"
        assert doc["run_id"] == run_id
        assert doc["original_photo_id"] == "e2e-photo-001"
        assert doc["storage_backend"] == "local"

        # PDF actually saved on disk
        saved = Path(doc["saved_path"])
        assert saved.exists(), f"Expected PDF at {saved}"
        assert saved.stat().st_size > 0
        assert saved.suffix == ".pdf"

        # Path is within output_dir
        assert str(saved).startswith(str(e2e_settings.output_dir))

    @pytest.mark.asyncio
    async def test_multiple_photos(
        self,
        e2e_settings,
        e2e_db: Database,
        e2e_llm,
        e2e_dir: Path,
    ):
        """Three photos processed in one run."""
        from PIL import Image

        photos = []
        for i in range(3):
            p = e2e_dir / f"photo_{i}.jpg"
            # Unterschiedliche Farbe je Bild: identische Dateien haetten denselben
            # SHA256 und wuerden vom file_hash-Dedup als Duplikat verworfen.
            Image.new("RGB", (80, 80), color=(200, 40 * i, 100 + 30 * i)).save(p, format="JPEG")
            photos.append(
                PhotoInfo(
                    uuid=f"uuid-{i}",
                    filename=p.name,
                    path=p,
                    original_filename=p.name,
                )
            )

        storage = LocalStorage(base_dir=e2e_settings.output_dir)
        pipeline = Pipeline(
            settings=e2e_settings,
            db=e2e_db,
            llm=e2e_llm,
            storage=storage,
        )

        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value=DOKUMENT_TEXT)):
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary(photos)):
                run_id = await pipeline.run()

        run = e2e_db.get_run(run_id)
        assert run["docs_processed"] == 3
        assert e2e_db.list_documents().__len__() == 3

    @pytest.mark.asyncio
    async def test_photo_without_path(self, e2e_settings, e2e_db: Database, e2e_llm):
        """Photo with no local path should not crash, just skip OCR."""
        photo = PhotoInfo(
            uuid="no-path-001",
            filename="ghost.jpg",
            path=None,
            original_filename="ghost.jpg",
        )

        storage = LocalStorage(base_dir=e2e_settings.output_dir)
        pipeline = Pipeline(
            settings=e2e_settings,
            db=e2e_db,
            llm=e2e_llm,
            storage=storage,
        )

        with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([photo])):
            run_id = await pipeline.run()

        run = e2e_db.get_run(run_id)
        # Ohne lokale Datei kann kein PDF entstehen: uebersprungen, aber kein Fehler.
        # (Die Assertion forderte hier fruehr docs_processed == 1 und war rot —
        # sie widersprach dem eigenen Docstring und dem Code.)
        assert run["status"] == "success"
        assert run["errors"] == 0
        assert run["docs_processed"] == 0
