"""Unit-Tests fuer die Lazy-Iteratoren und den Scan-Cutoff in photos.py."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from docflow.photos import (
    MockPhotosLibrary,
    PhotoInfo,
    _added_before_cutoff,
    cleanup_temp_export,
)


def _foto(uuid: str, *, added: datetime | None = None, taken: datetime | None = None,
          name: str | None = None) -> PhotoInfo:
    return PhotoInfo(
        uuid=uuid,
        filename=name or f"{uuid}.heic",
        path=None,
        original_filename=name or f"{uuid}.heic",
        date=taken,
        photo_date=taken,
        date_added=added,
    )


@pytest.mark.unit
class TestAddedBeforeCutoff:
    def test_fehlende_angaben_ueberspringen_nie(self):
        assert _added_before_cutoff(None, datetime(2026, 6, 1)) is False
        assert _added_before_cutoff(datetime(2026, 6, 1), None) is False
        assert _added_before_cutoff(None, None) is False

    def test_naiv_vor_und_nach(self):
        cutoff = datetime(2026, 6, 10)
        assert _added_before_cutoff(datetime(2026, 6, 1), cutoff) is True
        assert _added_before_cutoff(datetime(2026, 6, 20), cutoff) is False

    def test_gleichstand_gilt_nicht_als_vorher(self):
        cutoff = datetime(2026, 6, 10, 12, 0)
        assert _added_before_cutoff(cutoff, cutoff) is False

    def test_tz_aware_gegen_naiv_wirft_nicht(self):
        """osxphotos liefert tz-aware, der Scan-Stand ist naives UTC.

        Ein direkter Vergleich wuerfe TypeError — genau der Fehler, der den
        inkrementellen Scan frueher zum Absturz brachte.
        """
        cutoff = datetime(2026, 6, 10, 0, 0, 0)  # naives UTC
        plus2 = timezone(timedelta(hours=2))
        # 2026-06-09 23:00+02:00 == 21:00 UTC -> vor dem Cutoff
        assert _added_before_cutoff(datetime(2026, 6, 9, 23, 0, tzinfo=plus2), cutoff) is True
        # 2026-06-10 05:00+02:00 == 03:00 UTC -> danach
        assert _added_before_cutoff(datetime(2026, 6, 10, 5, 0, tzinfo=plus2), cutoff) is False

    def test_beide_tz_aware(self):
        plus2 = timezone(timedelta(hours=2))
        cutoff = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
        assert _added_before_cutoff(datetime(2026, 6, 10, 13, 0, tzinfo=plus2), cutoff) is True


@pytest.mark.unit
class TestMockIteratoren:
    def test_cutoff_filtert_alte_aufnahmen(self):
        lib = MockPhotosLibrary([
            _foto("alt", added=datetime(2026, 5, 1)),
            _foto("neu", added=datetime(2026, 6, 15)),
        ])
        out = list(lib.iter_all_photos(scan_cutoff=datetime(2026, 6, 1)))
        assert [p.uuid for p in out] == ["neu"]

    def test_ohne_cutoff_kommen_alle(self):
        lib = MockPhotosLibrary([
            _foto("a", added=datetime(2026, 5, 1)),
            _foto("b", added=datetime(2026, 6, 15)),
        ])
        assert len(list(lib.iter_all_photos())) == 2

    def test_aufnahme_ohne_date_added_bleibt_drin(self):
        """Im Zweifel pruefen statt verlieren."""
        lib = MockPhotosLibrary([_foto("unbekannt", added=None)])
        assert len(list(lib.iter_all_photos(scan_cutoff=datetime(2026, 6, 1)))) == 1

    def test_datumsbereich(self):
        lib = MockPhotosLibrary([
            _foto("frueh", taken=datetime(2026, 1, 15)),
            _foto("mitte", taken=datetime(2026, 6, 15)),
            _foto("spaet", taken=datetime(2026, 12, 15)),
        ])
        out = list(lib.iter_all_photos(date_from=date(2026, 6, 1), date_to=date(2026, 6, 30)))
        assert [p.uuid for p in out] == ["mitte"]

    def test_datumsbereich_ohne_aufnahmedatum_bleibt_drin(self):
        lib = MockPhotosLibrary([_foto("kein_datum", taken=None)])
        out = list(lib.iter_all_photos(date_from=date(2026, 6, 1)))
        assert len(out) == 1

    def test_zaehlen_ohne_dateizugriff(self):
        lib = MockPhotosLibrary([
            _foto("a", added=datetime(2026, 5, 1)),
            _foto("b", added=datetime(2026, 6, 15)),
        ])
        assert lib.count_all_photos() == 2
        assert lib.count_all_photos(scan_cutoff=datetime(2026, 6, 1)) == 1

    def test_iteratoren_sind_lazy(self):
        """Der Generator darf nicht vorab die ganze Liste durchlaufen."""
        lib = MockPhotosLibrary([_foto(str(i)) for i in range(100)])
        it = lib.iter_all_photos()
        erstes = next(it)
        assert erstes.uuid == "0"

    def test_uuids_in_albums(self):
        lib = MockPhotosLibrary([_foto("a"), _foto("b")])
        assert lib.uuids_in_albums({"Dokumente"}) == {"a", "b"}
        assert lib.uuids_in_albums(set()) == set()
        assert lib.uuids_in_albums({"  "}) == set()


@pytest.mark.unit
class TestCleanupTempExport:
    def test_none_ist_harmlos(self):
        cleanup_temp_export(None)  # darf nicht werfen

    def test_fremde_pfade_bleiben_unberuehrt(self, tmp_path):
        """Schutz gegen das Loeschen von Originalen in der Photos-Library."""
        datei = tmp_path / "original.heic"
        datei.write_bytes(b"x")
        cleanup_temp_export(datei)
        assert datei.exists()

    def test_eigener_export_wird_entfernt(self, tmp_path, monkeypatch):
        import tempfile as _tempfile

        monkeypatch.setattr(_tempfile, "gettempdir", lambda: str(tmp_path))
        export_dir = tmp_path / "docflow_export_abc"
        export_dir.mkdir()
        datei = export_dir / "IMG_1.jpg"
        datei.write_bytes(b"x")
        cleanup_temp_export(datei)
        assert not export_dir.exists()
