"""Unit tests for the pipeline (mocked OCR + LLM + storage)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from docflow.config import Settings
from docflow.db import Database
from docflow.llm.base import DocumentClassification
from docflow.photos import MockPhotosLibrary, PhotoInfo
from docflow.pipeline import Pipeline, _destination_path, _safe_filename
from tests.conftest import FAKE_CLASSIFICATION

# Oberhalb der Pre-Classifier-Schwelle (250 Zeichen): diese Tests pruefen den
# Verarbeitungspfad, nicht die Vorentscheidung. Ein Kurztext wuerde als Foto
# aussortiert — dafuer gibt es test_photo_wird_aussortiert.
DOKUMENT_TEXT = (
    "Vodafone GmbH\nRechnung Nr. 2026-4711\nDatum: 12.09.2026\n"
    "Kundennummer: 998877\nMobilfunk September 2026\n"
    "Grundgebuehr 29,99 EUR\nVerbrauch 15,01 EUR\n"
    "Netto 37,82 EUR\nMwSt 19 Prozent 7,18 EUR\nGesamtbetrag 45,00 EUR\n"
    "Zahlbar bis 26.09.2026 per Lastschrift.\n"
)


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
            "docflow.pipeline.extract_text", new=AsyncMock(return_value=DOKUMENT_TEXT)
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

        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value=DOKUMENT_TEXT)):
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

        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value=DOKUMENT_TEXT)):
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

        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value=DOKUMENT_TEXT)):
            pipeline = Pipeline(settings=settings, db=db, llm=mock_llm, storage=storage)
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([photo])):
                await pipeline.run()

        docs = db.list_documents()
        assert len(docs) == 1
        saved_path = Path(docs[0]["saved_path"])
        assert saved_path.exists()
        assert saved_path.suffix == ".pdf"
        assert saved_path.stat().st_size > 0


@pytest.mark.unit
class TestPreClassifierIntegration:
    """Die Vorentscheidung im Pipelinelauf: was gar nicht zum LLM gehen darf."""

    @staticmethod
    def _storage(settings: Settings):
        from docflow.storage.local import LocalStorage

        return LocalStorage(base_dir=settings.output_dir)

    @pytest.mark.asyncio
    async def test_textarmes_foto_wird_aussortiert(
        self, settings: Settings, db: Database, fake_image: Path, mock_llm
    ):
        """Ein Foto ohne verwertbaren Text kostet keinen LLM-Aufruf."""
        settings.force_document_albums = ""  # Vorpruefung aktiv lassen
        photo = PhotoInfo(
            uuid="foto-001", filename="IMG_0001.jpg", path=fake_image,
            original_filename="IMG_0001.jpg",
        )

        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value="Ausgang")):
            pipeline = Pipeline(
                settings=settings, db=db, llm=mock_llm, storage=self._storage(settings)
            )
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([photo])):
                run_id = await pipeline.run()

        run = db.get_run(run_id)
        assert run["docs_processed"] == 0
        assert run["errors"] == 0
        mock_llm.classify_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_aussortiertes_foto_wird_vermerkt(
        self, settings: Settings, db: Database, fake_image: Path, mock_llm
    ):
        """Der Vermerk ist noetig, damit der naechste Lauf nicht erneut OCRt."""
        settings.force_document_albums = ""
        photo = PhotoInfo(
            uuid="foto-002", filename="IMG_0002.jpg", path=fake_image,
            original_filename="IMG_0002.jpg",
        )

        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value="")):
            pipeline = Pipeline(
                settings=settings, db=db, llm=mock_llm, storage=self._storage(settings)
            )
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([photo])):
                await pipeline.run()

        docs = db.list_documents()
        assert len(docs) == 1
        assert docs[0]["doc_type"] == "Foto"
        assert docs[0]["original_photo_id"] == "foto-002"
        assert docs[0]["saved_path"] is None
        # OCR-Text bewusst nicht persistiert
        assert not docs[0]["ocr_text"]
        # und beim naechsten Lauf greift der UUID-Dedup
        assert db.document_exists(photo_id="foto-002")

    @pytest.mark.asyncio
    async def test_video_wird_nie_exportiert(
        self, settings: Settings, db: Database, mock_llm
    ):
        """Videos werden vor jedem Dateizugriff aussortiert (path=None genuegt)."""
        settings.force_document_albums = ""
        photo = PhotoInfo(
            uuid="video-001", filename="IMG_0003.MOV", path=None,
            original_filename="IMG_0003.MOV",
        )

        ocr = AsyncMock(return_value=DOKUMENT_TEXT)
        with patch("docflow.pipeline.extract_text", new=ocr):
            pipeline = Pipeline(
                settings=settings, db=db, llm=mock_llm, storage=self._storage(settings)
            )
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([photo])):
                run_id = await pipeline.run()

        run = db.get_run(run_id)
        assert run["docs_processed"] == 0
        assert run["errors"] == 0
        ocr.assert_not_called()
        mock_llm.classify_document.assert_not_called()
        docs = db.list_documents()
        assert len(docs) == 1 and docs[0]["doc_type"] == "Video"

    @pytest.mark.asyncio
    async def test_force_document_album_umgeht_vorpruefung(
        self, settings: Settings, db: Database, fake_image: Path, mock_llm
    ):
        """In der eigenen Dokumentenablage wird auch textarmes Material klassifiziert."""
        settings.photos_source = "album"
        settings.photos_album = "Dokumente"
        settings.force_document_albums = "Dokumente"
        photo = PhotoInfo(
            uuid="scan-001", filename="scan.jpg", path=fake_image,
            original_filename="scan.jpg",
        )

        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value="kurz")):
            pipeline = Pipeline(
                settings=settings, db=db, llm=mock_llm, storage=self._storage(settings)
            )
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([photo])):
                run_id = await pipeline.run()

        assert db.get_run(run_id)["docs_processed"] == 1
        mock_llm.classify_document.assert_called_once()


@pytest.mark.unit
class TestInkrementellerScan:
    """Scan-Stand lesen, anwenden und fortschreiben."""

    @staticmethod
    def _storage(settings: Settings):
        from docflow.storage.local import LocalStorage

        return LocalStorage(base_dir=settings.output_dir)

    def _pipeline(self, settings: Settings, db: Database, llm):
        return Pipeline(settings=settings, db=db, llm=llm, storage=self._storage(settings))

    @pytest.mark.asyncio
    async def test_erstlauf_schreibt_scan_stand(
        self, settings: Settings, db: Database, fake_image: Path, mock_llm
    ):
        photo = PhotoInfo(
            uuid="inc-001", filename="a.jpg", path=fake_image, original_filename="a.jpg",
            date_added=datetime(2026, 6, 1),
        )
        assert db.get_scan_state(settings.photos_album) is None

        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value=DOKUMENT_TEXT)):
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([photo])):
                await self._pipeline(settings, db, mock_llm).run()

        state = db.get_scan_state(settings.photos_album)
        assert state is not None
        assert state["last_scanned_at"]
        assert state["total_scanned"] == 1

    @pytest.mark.asyncio
    async def test_zweiter_lauf_ueberspringt_alte_aufnahmen(
        self, settings: Settings, db: Database, fake_image: Path, mock_llm
    ):
        """Nach einem Lauf darf dieselbe alte Aufnahme nicht erneut geprueft werden."""
        db.update_scan_state(settings.photos_album, datetime(2026, 6, 10), 1)
        alt = PhotoInfo(
            uuid="inc-alt", filename="alt.jpg", path=fake_image, original_filename="alt.jpg",
            date_added=datetime(2026, 6, 1),
        )
        ocr = AsyncMock(return_value=DOKUMENT_TEXT)
        with patch("docflow.pipeline.extract_text", new=ocr):
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([alt])):
                run_id = await self._pipeline(settings, db, mock_llm).run()

        run = db.get_run(run_id)
        assert run["photos_found"] == 0
        ocr.assert_not_called()
        mock_llm.classify_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_neue_aufnahme_kommt_durch(
        self, settings: Settings, db: Database, fake_image: Path, mock_llm
    ):
        db.update_scan_state(settings.photos_album, datetime(2026, 6, 10), 0)
        neu = PhotoInfo(
            uuid="inc-neu", filename="neu.jpg", path=fake_image, original_filename="neu.jpg",
            date_added=datetime(2026, 6, 20),
        )
        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value=DOKUMENT_TEXT)):
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([neu])):
                run_id = await self._pipeline(settings, db, mock_llm).run()

        assert db.get_run(run_id)["docs_processed"] == 1

    @pytest.mark.asyncio
    async def test_datumsfilter_ignoriert_scan_stand(
        self, settings: Settings, db: Database, fake_image: Path, mock_llm
    ):
        """Ein manuelles Fenster soll auch schon gesehene Aufnahmen erfassen."""
        db.update_scan_state(settings.photos_album, datetime(2026, 6, 10), 1)
        alt = PhotoInfo(
            uuid="inc-manuell", filename="alt.jpg", path=fake_image, original_filename="alt.jpg",
            date_added=datetime(2026, 6, 1), date=datetime(2026, 5, 5),
            photo_date=datetime(2026, 5, 5),
        )
        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value=DOKUMENT_TEXT)):
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([alt])):
                run_id = await self._pipeline(settings, db, mock_llm).run(
                    date_from=date(2026, 5, 1), date_to=date(2026, 5, 31)
                )

        assert db.get_run(run_id)["docs_processed"] == 1
        # und der Scan-Stand bleibt unangetastet
        assert db.get_scan_state(settings.photos_album)["last_scanned_at"].startswith("2026-06-10")

    @pytest.mark.asyncio
    async def test_vollscan_nutzt_eigenen_schluessel(
        self, settings: Settings, db: Database, fake_image: Path, mock_llm
    ):
        """album- und Vollscan fuehren getrennte Scan-Staende."""
        photo = PhotoInfo(
            uuid="inc-all", filename="a.jpg", path=fake_image, original_filename="a.jpg",
            date_added=datetime(2026, 6, 1),
        )
        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value=DOKUMENT_TEXT)):
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([photo])):
                await self._pipeline(settings, db, mock_llm).run(album_override="__all__")

        assert db.get_scan_state("__all__") is not None
        assert db.get_scan_state(settings.photos_album) is None

    @pytest.mark.asyncio
    async def test_uebersprungene_werden_gezaehlt(
        self, settings: Settings, db: Database, fake_image: Path, mock_llm
    ):
        settings.force_document_albums = ""
        photos = [
            PhotoInfo(uuid=f"skip-{i}", filename=f"f{i}.jpg", path=fake_image,
                      original_filename=f"f{i}.jpg")
            for i in range(2)
        ]
        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value="")):
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary(photos)):
                run_id = await self._pipeline(settings, db, mock_llm).run()

        run = db.get_run(run_id)
        assert run["docs_processed"] == 0
        assert run["photos_skipped"] == 2

    @pytest.mark.asyncio
    async def test_total_scanned_ist_bereichsgroesse(
        self, settings: Settings, db: Database, fake_image: Path, mock_llm
    ):
        """total_scanned zaehlt den Bereich, nicht die inkrementell geprueften.

        Sonst stuerzt der Wert nach dem ersten inkrementellen Lauf auf 0 ab und
        die Statistik im Scan-Stand ist wertlos.
        """
        db.update_scan_state(settings.photos_album, datetime(2026, 6, 10), 2)
        photos = [
            PhotoInfo(uuid="ts-alt", filename="alt.jpg", path=fake_image,
                      original_filename="alt.jpg", date_added=datetime(2026, 6, 1)),
            PhotoInfo(uuid="ts-neu", filename="neu.jpg", path=fake_image,
                      original_filename="neu.jpg", date_added=datetime(2026, 6, 20)),
        ]
        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value=DOKUMENT_TEXT)):
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary(photos)):
                run_id = await self._pipeline(settings, db, mock_llm).run()

        # nur die neue Aufnahme wurde geprueft ...
        assert db.get_run(run_id)["photos_found"] == 1
        # ... aber der Bereich umfasst beide
        assert db.get_scan_state(settings.photos_album)["total_scanned"] == 2


@pytest.mark.unit
class TestTempAufraeumen:
    """iCloud-Kopien duerfen auf keinem Weg liegen bleiben.

    Regression: die Aufraeumlogik stand im finally des PDF-Blocks, also hinter
    der Klassifikation. Aussortierte Fotos (der haeufigste Fall) liefen vorher
    daran vorbei — pro Nachtlauf blieben Dutzende HEIC-Kopien im
    Temp-Verzeichnis liegen.
    """

    @staticmethod
    def _storage(settings: Settings):
        from docflow.storage.local import LocalStorage

        return LocalStorage(base_dir=settings.output_dir)

    @staticmethod
    def _temp_export(tmp_path: Path, monkeypatch) -> Path:
        """Ein Export-Verzeichnis nachbauen, wie der iCloud-Download es anlegt."""
        import tempfile as _tempfile

        monkeypatch.setattr(_tempfile, "gettempdir", lambda: str(tmp_path))
        export_dir = tmp_path / "docflow_export_test1"
        export_dir.mkdir()
        bild = export_dir / "IMG_9999.jpg"
        from PIL import Image

        Image.new("RGB", (60, 60), color=(1, 2, 3)).save(bild, format="JPEG")
        return bild

    async def _lauf(self, settings, db, mock_llm, bild, ocr_text):
        photo = PhotoInfo(
            uuid="tmp-001", filename="IMG_9999.jpg", path=bild,
            original_filename="IMG_9999.jpg",
        )
        with patch("docflow.pipeline.extract_text", new=AsyncMock(return_value=ocr_text)):
            with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([photo])):
                pipeline = Pipeline(
                    settings=settings, db=db, llm=mock_llm, storage=self._storage(settings)
                )
                await pipeline.run()

    @pytest.mark.asyncio
    async def test_aussortiertes_foto_raeumt_auf(
        self, settings: Settings, db: Database, tmp_path: Path, mock_llm, monkeypatch
    ):
        settings.force_document_albums = ""
        bild = self._temp_export(tmp_path, monkeypatch)
        await self._lauf(settings, db, mock_llm, bild, "")
        assert not bild.exists()
        assert not bild.parent.exists()

    @pytest.mark.asyncio
    async def test_verarbeitetes_dokument_raeumt_auf(
        self, settings: Settings, db: Database, tmp_path: Path, mock_llm, monkeypatch
    ):
        bild = self._temp_export(tmp_path, monkeypatch)
        await self._lauf(settings, db, mock_llm, bild, DOKUMENT_TEXT)
        assert db.list_documents()[0]["doc_type"] == "Rechnung"
        assert not bild.parent.exists()

    @pytest.mark.asyncio
    async def test_dedup_raeumt_auf(
        self, settings: Settings, db: Database, tmp_path: Path, mock_llm, monkeypatch
    ):
        """Auch wenn die Aufnahme schon bekannt ist, wurde sie vorher geladen."""
        db.insert_document(
            run_id=db.create_run(), original_photo_id="tmp-001",
            original_filename="IMG_9999.jpg", ocr_text="", llm_provider=None,
            doc_type="Foto", tags=[], suggested_filename="IMG_9999.jpg", saved_path=None,
        )
        bild = self._temp_export(tmp_path, monkeypatch)
        await self._lauf(settings, db, mock_llm, bild, DOKUMENT_TEXT)
        assert not bild.parent.exists()

    @pytest.mark.asyncio
    async def test_originale_werden_nie_angefasst(
        self, settings: Settings, db: Database, tmp_path: Path, mock_llm, monkeypatch
    ):
        """Nur Pfade im Temp-Verzeichnis mit unserem Praefix werden geloescht."""
        settings.force_document_albums = ""
        import tempfile as _tempfile

        monkeypatch.setattr(_tempfile, "gettempdir", lambda: str(tmp_path / "tmp"))
        original = tmp_path / "Photos Library" / "IMG_1.jpg"
        original.parent.mkdir(parents=True)
        from PIL import Image

        Image.new("RGB", (60, 60)).save(original, format="JPEG")

        await self._lauf(settings, db, mock_llm, original, "")
        assert original.exists(), "Ein Original in der Photos-Library darf nie geloescht werden"
