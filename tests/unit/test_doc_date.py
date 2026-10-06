"""Dokumentdatum: LLM-Vorschlag pruefen, sonst Fotodatum (doc_date.py)."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from docflow.doc_date import (
    ParsedDate,
    apply_date_prefix,
    date_in_text,
    is_plausible,
    parse_llm_date,
    resolve_document_date,
    strip_date_prefix,
)

RECHNUNG = (
    "Vodafone GmbH\nRechnung Nr. 4711\nRechnungsdatum: 13.05.2024\n"
    "Zahlbar bis 27.05.2024\nGesamtbetrag 45,00 EUR\n"
)


@pytest.mark.unit
class TestParseLlmDate:
    def test_volles_datum(self):
        d = parse_llm_date("2024-05-13")
        assert d == ParsedDate(date(2024, 5, 13))
        assert d.iso == "2024-05-13"

    def test_nur_monat(self):
        d = parse_llm_date("2024-05")
        assert d is not None and d.month_only
        assert d.value == date(2024, 5, 1)
        assert d.iso == "2024-05"

    @pytest.mark.parametrize("raw", [None, "", "null", "unknown", "13.05.2024", "2024-13-01", "gestern"])
    def test_unbrauchbares_wird_none(self, raw):
        assert parse_llm_date(raw) is None


@pytest.mark.unit
class TestDateInText:
    @pytest.mark.parametrize(
        "text",
        [
            "Datum: 13.05.2024",
            "Datum: 13. 05. 2024",   # OCR streut Leerzeichen ein
            "Datum: 13.5.2024",
            "Datum: 13.05.24",
            "Datum: 2024-05-13",
            "Datum: 13/05/2024",
            "Datum: 05/13/2024",
            "Berlin, den 13. Mai 2024",
            "Berlin, 13.Mai 2024",
            "May 13, 2024",
            "13 May 2024",
        ],
    )
    def test_schreibweisen_fuer_volles_datum(self, text):
        assert date_in_text(ParsedDate(date(2024, 5, 13)), text)

    @pytest.mark.parametrize(
        "text",
        ["Mai 2024", "05/2024", "05.2024", "2024-05", "Abrechnung 13.05.2024", "MAI 2024"],
    )
    def test_schreibweisen_fuer_monat(self, text):
        assert date_in_text(ParsedDate(date(2024, 5, 1), month_only=True), text)

    def test_falsches_datum_wird_nicht_gefunden(self):
        assert not date_in_text(ParsedDate(date(2023, 5, 13)), RECHNUNG)

    def test_teilstring_zaehlt_nicht(self):
        # 113.05.2024 ist nicht der 13.05.2024
        assert not date_in_text(ParsedDate(date(2024, 5, 13)), "Nr. 113.05.2024")

    def test_betrag_ist_kein_monat(self):
        # "5.24 EUR" darf nicht als Mai 2024 durchgehen
        assert not date_in_text(ParsedDate(date(2024, 5, 1), month_only=True), "Summe 5.24 EUR")

    def test_leerer_text(self):
        assert not date_in_text(ParsedDate(date(2024, 5, 13)), "")


@pytest.mark.unit
class TestPlausibel:
    def test_altes_datum_unplausibel(self):
        assert not is_plausible(ParsedDate(date(1987, 1, 1)), date(2024, 1, 1))

    def test_ticket_in_naher_zukunft_ok(self):
        assert is_plausible(ParsedDate(date(2024, 10, 1)), date(2024, 3, 1))

    def test_jahre_nach_dem_foto_unplausibel(self):
        assert not is_plausible(ParsedDate(date(2027, 1, 1)), date(2024, 3, 1))

    def test_ohne_fotodatum_gilt_heute(self):
        assert is_plausible(ParsedDate(date(2020, 1, 1)), None)
        assert not is_plausible(ParsedDate(date(2099, 1, 1)), None)


@pytest.mark.unit
class TestResolveDocumentDate:
    FOTO = datetime(2026, 6, 10, 9, 30)

    def test_bestaetigtes_dokumentdatum_gewinnt(self):
        r = resolve_document_date("2024-05-13", "explicit", RECHNUNG, self.FOTO)
        assert r.source == "document"
        assert r.effective_date == date(2024, 5, 13)
        assert r.document_date_iso == "2024-05-13"
        assert r.effective_date_iso == "2024-05-13"

    def test_halluziniertes_datum_faellt_auf_foto_zurueck(self):
        # Das klassische "heute" von Haiku: steht nirgends im Text
        r = resolve_document_date("2023-05-01", "explicit", RECHNUNG, self.FOTO)
        assert r.source == "photo"
        assert r.effective_date == self.FOTO.date()
        assert r.document_date is None
        assert "nicht im OCR-Text" in r.reason

    def test_inferred_wird_nicht_uebernommen(self):
        # Das Faelligkeitsdatum steht zwar im Text, ist aber nicht das Dokumentdatum
        r = resolve_document_date("2024-05-27", "inferred", RECHNUNG, self.FOTO)
        assert r.source == "photo"
        assert r.document_date is None

    def test_unplausibles_datum_faellt_zurueck(self):
        text = "Gueltig bis 31.12.2031"
        r = resolve_document_date("2031-12-31", "explicit", text, self.FOTO)
        assert r.source == "photo"
        assert "unplausibel" in r.reason

    def test_nur_monat_wird_akzeptiert(self):
        r = resolve_document_date("2024-05", "explicit", "Abrechnung Mai 2024", self.FOTO)
        assert r.source == "document"
        assert r.document_date_iso == "2024-05"
        assert r.effective_date == date(2024, 5, 1)

    def test_ohne_alles_bleibt_nichts(self):
        r = resolve_document_date(None, "none", RECHNUNG, None)
        assert r.source == "none"
        assert r.effective_date is None
        assert r.effective_date_iso is None

    def test_kein_llm_datum_aber_foto(self):
        r = resolve_document_date(None, "none", RECHNUNG, date(2024, 8, 1))
        assert r.source == "photo"
        assert r.effective_date == date(2024, 8, 1)


@pytest.mark.unit
class TestDateiname:
    def test_llm_praefix_wird_ersetzt(self):
        assert strip_date_prefix("2023-05_Vodafone_Rechnung.pdf") == "Vodafone_Rechnung.pdf"
        assert strip_date_prefix("2023-05-13_Vodafone.pdf") == "Vodafone.pdf"
        assert strip_date_prefix("2023-05 Vodafone.pdf") == "Vodafone.pdf"

    def test_ohne_praefix_unveraendert(self):
        assert strip_date_prefix("Vodafone_Rechnung.pdf") == "Vodafone_Rechnung.pdf"

    def test_nur_praefix_bleibt_erhalten(self):
        # Sonst wuerde ein leerer Name entstehen
        assert strip_date_prefix("2023-05_") == "2023-05_"

    def test_praefix_aus_wirksamem_datum(self):
        assert apply_date_prefix("2023-05_Vodafone.pdf", date(2024, 5, 13)) == "2024-05_Vodafone.pdf"
        assert apply_date_prefix("Vodafone.pdf", datetime(2024, 5, 13, 8)) == "2024-05_Vodafone.pdf"

    def test_ohne_datum_kein_praefix(self):
        assert apply_date_prefix("2023-05_Vodafone.pdf", None) == "Vodafone.pdf"
