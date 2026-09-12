"""Unit-Tests fuer die Vorschaubilder."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from docflow.thumbnails import DEFAULT_MAX_PX, render_thumbnail


def _jpeg(pfad, groesse=(800, 600), farbe=(120, 160, 200)) -> None:
    Image.new("RGB", groesse, color=farbe).save(pfad, format="JPEG")


def _pdf_aus_bild(pfad, bildgroesse=(800, 600)) -> None:
    puffer = io.BytesIO()
    Image.new("RGB", bildgroesse, color=(200, 100, 50)).save(puffer, format="JPEG")
    import img2pdf

    pfad.write_bytes(img2pdf.convert(io.BytesIO(puffer.getvalue())))


@pytest.mark.unit
class TestRenderThumbnail:
    def test_fehlende_datei(self, tmp_path):
        assert render_thumbnail(tmp_path / "gibtsnicht.pdf") is None

    def test_verzeichnis_statt_datei(self, tmp_path):
        assert render_thumbnail(tmp_path) is None

    def test_bild_direkt(self, tmp_path):
        quelle = tmp_path / "scan.jpg"
        _jpeg(quelle)
        out = render_thumbnail(quelle)
        assert out is not None
        img = Image.open(io.BytesIO(out))
        assert max(img.size) <= DEFAULT_MAX_PX
        assert img.format == "JPEG"

    def test_pdf(self, tmp_path):
        quelle = tmp_path / "doc.pdf"
        _pdf_aus_bild(quelle)
        out = render_thumbnail(quelle)
        assert out is not None
        img = Image.open(io.BytesIO(out))
        assert max(img.size) <= DEFAULT_MAX_PX

    def test_groesse_wird_beachtet(self, tmp_path):
        quelle = tmp_path / "scan.jpg"
        _jpeg(quelle)
        out = render_thumbnail(quelle, max_px=64)
        img = Image.open(io.BytesIO(out))
        assert max(img.size) <= 64

    def test_seitenverhaeltnis_bleibt(self, tmp_path):
        quelle = tmp_path / "scan.jpg"
        _jpeg(quelle, groesse=(800, 400))
        img = Image.open(io.BytesIO(render_thumbnail(quelle, max_px=200)))
        assert img.size[0] > img.size[1]

    def test_kaputtes_pdf(self, tmp_path):
        quelle = tmp_path / "kaputt.pdf"
        quelle.write_bytes(b"keine PDF-Struktur")
        assert render_thumbnail(quelle) is None

    def test_kaputtes_bild(self, tmp_path):
        quelle = tmp_path / "kaputt.jpg"
        quelle.write_bytes(b"kein JPEG")
        assert render_thumbnail(quelle) is None

    def test_graustufen_wird_konvertiert(self, tmp_path):
        quelle = tmp_path / "grau.png"
        Image.new("P", (400, 400)).save(quelle, format="PNG")
        out = render_thumbnail(quelle)
        assert out is not None


@pytest.mark.unit
class TestCache:
    def test_zweiter_aufruf_kommt_aus_dem_cache(self, tmp_path, monkeypatch):
        quelle = tmp_path / "scan.jpg"
        _jpeg(quelle)
        cache = tmp_path / "cache"

        erst = render_thumbnail(quelle, cache_dir=cache)
        assert len(list(cache.glob("*.jpg"))) == 1

        # Die Erzeugung sabotieren: kommt trotzdem ein Bild, war es der Cache.
        # (Die Quelle darf nicht angetastet werden — ihre mtime ist Teil des
        # Cache-Schluessels, ein Neuschreiben wuerde den Eintrag entwerten.)
        from docflow import thumbnails

        monkeypatch.setattr(thumbnails, "_verkleinern", lambda *a, **k: None)
        zweit = render_thumbnail(quelle, cache_dir=cache)
        assert zweit == erst

    def test_geaenderte_quelle_erzeugt_neuen_eintrag(self, tmp_path):
        quelle = tmp_path / "scan.jpg"
        _jpeg(quelle, farbe=(10, 10, 10))
        cache = tmp_path / "cache"
        render_thumbnail(quelle, cache_dir=cache)

        # mtime aendern, damit der Cache-Schluessel nicht mehr passt
        import os
        import time

        _jpeg(quelle, farbe=(250, 250, 250))
        os.utime(quelle, (time.time() + 10, time.time() + 10))
        render_thumbnail(quelle, cache_dir=cache)

        assert len(list(cache.glob("*.jpg"))) == 2

    def test_keine_teildatei_bleibt_liegen(self, tmp_path):
        quelle = tmp_path / "scan.jpg"
        _jpeg(quelle)
        cache = tmp_path / "cache"
        render_thumbnail(quelle, cache_dir=cache)
        assert not list(cache.glob("*.part"))

    def test_unbeschreibbarer_cache_ist_kein_fehler(self, tmp_path, monkeypatch):
        quelle = tmp_path / "scan.jpg"
        _jpeg(quelle)

        from pathlib import Path as _Path

        def wirft(self, *a, **k):
            raise OSError("kein Platz")

        monkeypatch.setattr(_Path, "mkdir", wirft)
        # Das Bild muss trotzdem geliefert werden
        assert render_thumbnail(quelle, cache_dir=tmp_path / "cache") is not None


@pytest.mark.unit
class TestThumbnailEndpoint:
    """Der Endpoint loest die Datei ueber die DB auf, nie ueber die Anfrage."""

    @staticmethod
    def _client_und_db(settings):
        """Client samt DB unter settings.db_path.

        Die db-Fixture zeigt auf test.db, create_app oeffnet aber
        settings.db_path — hier muss also dieselbe Datei benutzt werden, sonst
        sieht die App die eingefuegten Dokumente nicht.
        """
        from fastapi.testclient import TestClient

        from docflow.db import Database
        from docflow.web.app import create_app

        client = TestClient(create_app(settings))
        return client, Database(settings.db_path)

    def test_unbekanntes_dokument(self, settings):
        client, _ = self._client_und_db(settings)
        assert client.get("/api/documents/999/thumbnail").status_code == 404

    def test_dokument_ohne_datei(self, settings):
        client, db = self._client_und_db(settings)
        db.insert_document(
            run_id=db.create_run(), original_photo_id="u1", original_filename="a.jpg",
            ocr_text="x", llm_provider="test", doc_type="Foto", tags=[],
            suggested_filename="a.jpg", saved_path=None,
        )
        assert client.get("/api/documents/1/thumbnail").status_code == 404

    def test_liefert_jpeg(self, settings, tmp_path):
        client, db = self._client_und_db(settings)
        pdf = tmp_path / "doc.pdf"
        _pdf_aus_bild(pdf)
        db.insert_document(
            run_id=db.create_run(), original_photo_id="u2", original_filename="doc.jpg",
            ocr_text="x", llm_provider="test", doc_type="Brief", tags=[],
            suggested_filename="doc.pdf", saved_path=str(pdf),
        )
        resp = client.get("/api/documents/1/thumbnail")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"
        assert "max-age" in resp.headers.get("cache-control", "")
        assert Image.open(io.BytesIO(resp.content)).format == "JPEG"

    def test_groesse_wird_begrenzt(self, settings, tmp_path):
        client, db = self._client_und_db(settings)
        pdf = tmp_path / "doc.pdf"
        _pdf_aus_bild(pdf, bildgroesse=(2000, 2000))
        db.insert_document(
            run_id=db.create_run(), original_photo_id="u3", original_filename="doc.jpg",
            ocr_text="x", llm_provider="test", doc_type="Brief", tags=[],
            suggested_filename="doc.pdf", saved_path=str(pdf),
        )
        # unsinnig gross -> gedeckelt
        gross = client.get("/api/documents/1/thumbnail?size=99999")
        assert max(Image.open(io.BytesIO(gross.content)).size) <= 1024
        # unsinnig klein -> Mindestmass
        klein = client.get("/api/documents/1/thumbnail?size=1")
        assert max(Image.open(io.BytesIO(klein.content)).size) >= 48
