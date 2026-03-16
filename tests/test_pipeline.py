"""Unit tests for the pipeline (mocked OCR + LLM + storage)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from docflow.config import Settings
from docflow.db import Database
from docflow.llm.base import DocumentClassification
from docflow.photos import MockPhotosLibrary, PhotoInfo
from docflow.pipeline import Pipeline, _destination_path, _safe_filename
from tests.conftest import FAKE_CLASSIFICATION


@pytest.mark.unit
class TestHelpers:
    def test_safe_filename_removes_bad_chars(self):
        name = "foo/bar:baz<>*?.pdf"
        result = _safe_filename(name)
        assert "/" not in result
        assert ":" not in result
        assert "<" not in result

    def test_safe_filename_truncates(self):
        long_name = "a" * 300 + ".pdf"
        result = _safe_filename(long_name)
        assert len(result) <= 200

    def test_destination_path_structure(self):
        from datetime import datetime

        cls = DocumentClassification(
            doc_type="Rechnung",
            tags=[],
            suggested_filename="2026-03_Test.pdf",
            confidence=0.9,
        )
        path = _destination_path(cls, datetime(2026, 3, 15))
        assert path.startswith("2026/03/")
        assert path.endswith(".pdf")

    def test_destination_path_adds_pdf_extension(self):
        from datetime import datetime

        cls = DocumentClassification(
            doc_type="Brief",
            tags=[],
            suggested_filename="no_extension",
            confidence=0.5,
        )
        path = _destination_path(cls, datetime(2026, 3, 15))
        assert path.endswith(".pdf")


@pytest.mark.unit
class TestPipeline:
    @pytest.mark.asyncio
    async def test_run_with_mock_photo(
        self,
        settings: Settings,
        db: Database,
        tmp_dir: Path,
        fake_image: Path,
        mock_llm,
    ):
        """Full pipeline run with a fake image, mock OCR, mock LLM."""
        photo = PhotoInfo(
            uuid="test-001",
            filename="doc.jpg",
            path=fake_image,
            original_filename="original.jpg",
        )

        from docflow.storage.local import LocalStorage

        storage = LocalStorage(base_dir=settings.output_dir)

        with patch(
            "docflow.pipeline.extract_text", new=AsyncMock(return_value="Rechnung Vodafone 45 EUR")
        ):
            pipeline = Pipeline(settings=settings, db=db, llm=mock_llm, storage=storage)
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([photo])):
                run_id = await pipeline.run()

        assert run_id == 1

        run = db.get_run(run_id)
        assert run["status"] == "success"
        assert run["docs_processed"] == 1
        assert run["errors"] == 0

        docs = db.list_documents()
        assert len(docs) == 1
        assert docs[0]["doc_type"] == FAKE_CLASSIFICATION.doc_type
        assert docs[0]["source"] == "photos"

    @pytest.mark.asyncio
    async def test_run_records_error_on_llm_failure(
        self,
        settings: Settings,
        db: Database,
        fake_image: Path,
    ):
        photo = PhotoInfo(
            uuid="bad-001",
            filename="bad.jpg",
            path=fake_image,
            original_filename="bad.jpg",
        )

        failing_llm = MagicMock()
        failing_llm.classify_document = AsyncMock(side_effect=RuntimeError("LLM down"))

        from docflow.storage.local import LocalStorage

        storage = LocalStorage(base_dir=settings.output_dir)

        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value="text")):
            pipeline = Pipeline(settings=settings, db=db, llm=failing_llm, storage=storage)
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([photo])):
                run_id = await pipeline.run()

        run = db.get_run(run_id)
        assert run["errors"] == 1

    @pytest.mark.asyncio
    async def test_run_with_photos_source_all(
        self,
        settings: Settings,
        db: Database,
        tmp_dir: Path,
        fake_image: Path,
        mock_llm,
    ):
        """Pipeline with photos_source='all' uses get_all_photos()."""
        settings.photos_source = "all"
        photo = PhotoInfo(
            uuid="all-001",
            filename="doc.jpg",
            path=fake_image,
            original_filename="original.jpg",
        )

        from docflow.storage.local import LocalStorage

        storage = LocalStorage(base_dir=settings.output_dir)
        mock_lib = MockPhotosLibrary([photo])

        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value="Some text")):
            pipeline = Pipeline(settings=settings, db=db, llm=mock_llm, storage=storage)
            with patch("docflow.pipeline.get_library", return_value=mock_lib):
                run_id = await pipeline.run()

        run = db.get_run(run_id)
        assert run["status"] == "success"
        assert run["docs_processed"] == 1

    @pytest.mark.asyncio
    async def test_run_empty_album(
        self,
        settings: Settings,
        db: Database,
        mock_llm,
    ):
        from docflow.storage.local import LocalStorage

        storage = LocalStorage(base_dir=settings.output_dir)
        pipeline = Pipeline(settings=settings, db=db, llm=mock_llm, storage=storage)

        with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([])):
            run_id = await pipeline.run()

        run = db.get_run(run_id)
        assert run["docs_processed"] == 0
        assert run["errors"] == 0
        assert run["status"] == "success"

    @pytest.mark.asyncio
    async def test_saved_pdf_exists(
        self,
        settings: Settings,
        db: Database,
        fake_image: Path,
        mock_llm,
    ):
        photo = PhotoInfo(
            uuid="pdf-001",
            filename="doc.jpg",
            path=fake_image,
            original_filename="doc.jpg",
        )

        from docflow.storage.local import LocalStorage

        storage = LocalStorage(base_dir=settings.output_dir)

        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value="text")):
            pipeline = Pipeline(settings=settings, db=db, llm=mock_llm, storage=storage)
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([photo])):
                await pipeline.run()

        docs = db.list_documents()
        assert len(docs) == 1
        saved_path = Path(docs[0]["saved_path"])
        assert saved_path.exists()
        assert saved_path.suffix == ".pdf"
        assert saved_path.stat().st_size > 0
