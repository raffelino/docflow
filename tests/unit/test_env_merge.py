"""Unit-Tests fuer das Schreiben der .env aus den Einstellungen.

Der Kern ist die Merge-Logik: die .env enthaelt Werte, die die Settings-Maske
nicht kennt — vor allem ``OPENROUTER_API_KEY``. Ein vollstaendiges Neuschreiben
loescht sie, und der naechste Pipelinelauf scheitert an der Klassifikation.
"""

from __future__ import annotations

import pytest

from docflow.web.routes import (
    _READONLY_FIELDS,
    _SETTINGS_FIELDS,
    _format_env_value,
    _write_env_file,
)


def _werte(pfad) -> dict[str, str]:
    """.env als Schluessel/Wert lesen (Kommentare ignoriert)."""
    out = {}
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        blank = zeile.strip()
        if blank and not blank.startswith("#") and "=" in blank:
            k, v = blank.split("=", 1)
            out[k.strip()] = v
    return out


@pytest.mark.unit
class TestFormatEnvValue:
    def test_bool_klein(self):
        assert _format_env_value(True) == "true"
        assert _format_env_value(False) == "false"

    def test_zahl_und_text(self):
        assert _format_env_value(8765) == "8765"
        assert _format_env_value("INBOX") == "INBOX"

    def test_pfad(self, tmp_path):
        assert _format_env_value(tmp_path) == str(tmp_path)


@pytest.mark.unit
class TestWriteEnvFile:
    def test_api_key_ueberlebt(self, settings, tmp_path):
        """Der wichtigste Fall: fremde Eintraege bleiben stehen."""
        env = tmp_path / ".env"
        env.write_text(
            "OPENROUTER_API_KEY=sk-or-v1-geheim\n"
            "PHOTOS_ALBUM=Dokumente\n"
            "ANTHROPIC_API_KEY=sk-ant-auch-geheim\n",
            encoding="utf-8",
        )

        _write_env_file(settings, env)

        werte = _werte(env)
        assert werte["OPENROUTER_API_KEY"] == "sk-or-v1-geheim"
        assert werte["ANTHROPIC_API_KEY"] == "sk-ant-auch-geheim"

    def test_bekannter_wert_wird_aktualisiert(self, settings, tmp_path):
        env = tmp_path / ".env"
        env.write_text("PHOTOS_ALBUM=AltesAlbum\n", encoding="utf-8")

        _write_env_file(settings, env)

        assert _werte(env)["PHOTOS_ALBUM"] == settings.photos_album

    def test_kommentare_und_leerzeilen_bleiben(self, settings, tmp_path):
        env = tmp_path / ".env"
        env.write_text(
            "# Wichtiger Hinweis\n"
            "\n"
            "OPENROUTER_API_KEY=sk-or-v1-geheim\n"
            "# noch ein Kommentar\n",
            encoding="utf-8",
        )

        _write_env_file(settings, env)

        inhalt = env.read_text(encoding="utf-8")
        assert "# Wichtiger Hinweis" in inhalt
        assert "# noch ein Kommentar" in inhalt

    def test_reihenfolge_bleibt(self, settings, tmp_path):
        env = tmp_path / ".env"
        env.write_text(
            "OPENROUTER_API_KEY=sk-or-v1-geheim\nPHOTOS_ALBUM=Alt\nWEB_PORT=1234\n",
            encoding="utf-8",
        )

        _write_env_file(settings, env)

        zeilen = [z for z in env.read_text(encoding="utf-8").splitlines() if "=" in z]
        assert zeilen[0].startswith("OPENROUTER_API_KEY=")
        assert zeilen[1].startswith("PHOTOS_ALBUM=")

    def test_fehlende_felder_werden_angehaengt(self, settings, tmp_path):
        env = tmp_path / ".env"
        env.write_text("OPENROUTER_API_KEY=sk-or-v1-geheim\n", encoding="utf-8")

        _write_env_file(settings, env)

        werte = _werte(env)
        for field in _SETTINGS_FIELDS:
            assert field.upper() in werte

    def test_ohne_vorhandene_datei(self, settings, tmp_path):
        env = tmp_path / ".env"
        _write_env_file(settings, env)
        werte = _werte(env)
        assert werte["PHOTOS_ALBUM"] == settings.photos_album

    def test_zweimal_schreiben_bleibt_stabil(self, settings, tmp_path):
        """Kein Anwachsen der Datei bei wiederholtem Speichern."""
        env = tmp_path / ".env"
        env.write_text("OPENROUTER_API_KEY=sk-or-v1-geheim\n", encoding="utf-8")

        _write_env_file(settings, env)
        erst = env.read_text(encoding="utf-8")
        _write_env_file(settings, env)
        assert env.read_text(encoding="utf-8") == erst

    def test_wert_mit_gleichheitszeichen_bleibt_ganz(self, settings, tmp_path):
        env = tmp_path / ".env"
        env.write_text("SOME_TOKEN=abc==def==\n", encoding="utf-8")
        _write_env_file(settings, env)
        assert _werte(env)["SOME_TOKEN"] == "abc==def=="


@pytest.mark.unit
class TestReadonlyFields:
    def test_kritische_felder_sind_geschuetzt(self):
        assert "photos_source" in _READONLY_FIELDS
        assert "llm_provider" in _READONLY_FIELDS
        assert "web_host" in _READONLY_FIELDS

    def test_geschuetzte_felder_bleiben_sichtbar(self):
        """Anzeigen ja, aendern nein — sonst wirkt die Maske kaputt."""
        for field in _READONLY_FIELDS:
            assert field in _SETTINGS_FIELDS


@pytest.mark.unit
class TestSortierung:
    """Sortierfelder werden zugeordnet, nicht durchgereicht (SQL-Injection)."""

    def test_nur_bekannte_felder(self):
        from docflow.db import Database

        assert "created_at" in Database.SORT_COLUMNS
        assert "doc_type" in Database.SORT_COLUMNS
        # der Spaltenname wird interpoliert, darum feste Zuordnung
        assert "filename" in Database.SORT_COLUMNS
        assert Database.SORT_COLUMNS["filename"] == "suggested_filename"

    def test_unbekanntes_feld_faellt_auf_default(self, db):
        db.list_documents(sort="'; DROP TABLE documents; --")
        # kein Fehler, Tabelle steht noch
        assert db.list_documents() == []

    def test_richtung_wird_normalisiert(self, db, tmp_path):
        for i in range(3):
            db.insert_document(
                run_id=db.create_run(), original_photo_id=f"u{i}",
                original_filename=f"f{i}.jpg", ocr_text="x", llm_provider="test",
                doc_type="Brief", tags=[], suggested_filename=f"f{i}.pdf",
                saved_path=str(tmp_path / f"f{i}.pdf"),
            )
        auf = [d["id"] for d in db.list_documents(sort="created_at", order="asc")]
        ab = [d["id"] for d in db.list_documents(sort="created_at", order="desc")]
        assert auf == sorted(auf)
        assert ab == sorted(ab, reverse=True)
        # unsinnige Richtung -> absteigend
        assert [d["id"] for d in db.list_documents(order="seitwaerts")] == ab
