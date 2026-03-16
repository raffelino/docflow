"""E2E: fake album → OCR → LLM → PDF → DB check."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from docflow.db import Database
from docflow.photos import MockPhotosLibrary, PhotoInfo
from docflow.pipeline import Pipeline
from docflow.storage.local import LocalStorage


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
            new=AsyncMock(return_value="Vodafone GmbH Rechnung 45,00 EUR"),
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
            Image.new("RGB", (80, 80), color=(200, 200, 200)).save(p, format="JPEG")
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

        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value="some text")):
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
        # Should still succeed — just with empty OCR text
        assert run["docs_processed"] == 1
