"""Unit-Tests fuer die Vorentscheidung Dokument/Foto/Video.

Die Schwellwerte sind an echten Daten kalibriert (siehe Modul-Docstring von
``pre_classifier``): 200 Fotos der Library gegen 871 klassifizierte Dokumente
aus der Produktions-DB. Gemessene Wirkung der hier getesteten Regeln:
2,5 % der Fotos gelten als Dokument, 100 % der Dokumente werden erkannt.
"""

from __future__ import annotations

import pytest

from docflow.pre_classifier import (
    _VIDEO_EXTENSIONS,
    DEFAULT_MIN_CHARS,
    classify_media,
    is_video,
    looks_like_document,
)

# Realistischer Rechnungstext, oberhalb der Schwelle
RECHNUNG = (
    "Stadtwerke Muenchen GmbH\nRechnung Nr. 2026-8842\nDatum: 03.09.2026\n"
    "Kundennummer: 4711\nStromverbrauch August 2026: 312 kWh\n"
    "Netto 73,45 EUR\nMwSt 19 % 13,95 EUR\nGesamtbetrag 87,40 EUR\n"
    "Zahlbar bis 17.09.2026 auf IBAN DE02120300000000202051\n"
    "Bei Rueckfragen nennen Sie bitte Ihre Kundennummer.\n"
)


@pytest.mark.unit
class TestVideoErkennung:
    @pytest.mark.parametrize(
        "name",
        ["IMG_1234.MOV", "clip.mp4", "a.m4v", "b.avi", "c.mkv", "d.webm",
         "e.3gp", "f.m2ts", "g.mpeg", "kleinschreibung.mov"],
    )
    def test_videoformate(self, name):
        assert is_video(name) is True

    @pytest.mark.parametrize("name", ["a.heic", "b.HEIC", "c.jpg", "d.jpeg", "e.png", "f.pdf"])
    def test_keine_videos(self, name):
        assert is_video(name) is False

    def test_none_und_leer(self):
        assert is_video(None) is False
        assert is_video("") is False

    def test_endung_nur_am_ende(self):
        # "mov" mitten im Namen darf nicht greifen
        assert is_video("movie_poster.jpg") is False
        assert is_video("mp4_screenshot.png") is False

    def test_regex_wird_exportiert(self):
        # photos.py importiert das Muster direkt, um vor dem Export zu filtern
        assert _VIDEO_EXTENSIONS.search("x.mov")
        assert not _VIDEO_EXTENSIONS.search("x.heic")


@pytest.mark.unit
class TestDokumentHeuristik:
    def test_leerer_text_ist_kein_dokument(self):
        assert looks_like_document("") is False
        assert looks_like_document(None) is False

    def test_langer_text_ist_dokument(self):
        assert looks_like_document("a" * DEFAULT_MIN_CHARS) is True

    def test_knapp_unter_schwelle_ohne_signal(self):
        assert looks_like_document("a" * (DEFAULT_MIN_CHARS - 1)) is False

    def test_nur_whitespace_zaehlt_nicht(self):
        assert looks_like_document(" " * 400) is False

    def test_kurzer_text_mit_dokumentbegriff(self):
        # 120..249 Zeichen plus eindeutiger Begriff -> trotzdem Dokument
        text = "Quittung ueber den Betrag von 12,50 EUR. " + "x" * 100
        assert 120 <= len(text) < DEFAULT_MIN_CHARS
        assert looks_like_document(text) is True

    def test_sehr_kurzer_text_trotz_begriff_nicht(self):
        # unter 120 Zeichen ist die Signallage zu duenn
        assert looks_like_document("Rechnung") is False

    def test_echte_rechnung(self):
        assert looks_like_document(RECHNUNG) is True

    def test_schwelle_konfigurierbar(self):
        text = "a" * 300
        assert looks_like_document(text, min_chars=250) is True
        assert looks_like_document(text, min_chars=500) is False


@pytest.mark.unit
class TestClassifyMedia:
    def test_dokument(self):
        assert classify_media("scan.heic", RECHNUNG) == "document"

    def test_foto_ohne_text(self):
        assert classify_media("IMG_0001.heic", "") == "photo"

    def test_foto_mit_wenig_text(self):
        # typisches Strassenschild o.ae.
        assert classify_media("IMG_0002.heic", "Hauptstrasse 5\nEinbahn") == "photo"

    def test_video_vor_allem_anderen(self):
        assert classify_media("clip.mov", RECHNUNG) == "video"

    def test_video_schlaegt_force_document(self):
        # Auch in einem Dokumentenalbum gibt es fuer Videos keinen OCR-Pfad
        assert classify_media("clip.mov", "", force_document=True) == "video"

    def test_force_document_uebergeht_heuristik(self):
        assert classify_media("IMG_0003.heic", "", force_document=True) == "document"

    def test_force_document_bei_leerem_dateinamen(self):
        assert classify_media(None, None, force_document=True) == "document"

    def test_screenshot_eines_dokuments_wird_nicht_verworfen(self):
        """Regression: Screenshot-Muster darf kein Ausschlusskriterium sein.

        36,7 % der echten Dokumente in der Produktions-DB sehen wie ein
        iPhone-Screenshot aus (Uhrzeit + Mobilfunkanzeige) — Online-Rechnungen
        und Tickets. Wer darauf filtert, verliert sie.
        """
        text = "09:41\nLTE\n" + RECHNUNG
        assert classify_media("IMG_0004.png", text) == "document"
