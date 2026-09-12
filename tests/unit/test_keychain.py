"""Unit-Tests fuer das Lesen von Zugangsdaten aus dem macOS-Schluesselbund.

``security`` wird durchgaengig gemockt: die Tests duerfen weder den echten
Schluesselbund befragen noch einen Entsperrdialog ausloesen.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from docflow import keychain


def _ergebnis(returncode: int = 0, stdout: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")


@pytest.fixture
def verfuegbar(monkeypatch):
    monkeypatch.setattr(keychain, "is_available", lambda: True)


@pytest.mark.unit
class TestIsAvailable:
    def test_nur_auf_macos(self, monkeypatch):
        monkeypatch.setattr(keychain.sys, "platform", "linux")
        assert keychain.is_available() is False

    def test_ohne_security_werkzeug(self, monkeypatch):
        monkeypatch.setattr(keychain.sys, "platform", "darwin")
        monkeypatch.setattr(keychain.shutil, "which", lambda _: None)
        assert keychain.is_available() is False

    def test_auf_macos_mit_werkzeug(self, monkeypatch):
        monkeypatch.setattr(keychain.sys, "platform", "darwin")
        monkeypatch.setattr(keychain.shutil, "which", lambda _: "/usr/bin/security")
        assert keychain.is_available() is True


@pytest.mark.unit
class TestGetPassword:
    def test_leerer_account(self):
        assert keychain.get_password("") is None

    def test_nicht_verfuegbar(self, monkeypatch):
        monkeypatch.setattr(keychain, "is_available", lambda: False)
        assert keychain.get_password("wer@example.com") is None

    def test_treffer(self, monkeypatch, verfuegbar):
        monkeypatch.setattr(
            keychain.subprocess, "run", lambda *a, **k: _ergebnis(0, "geheim\n")
        )
        assert keychain.get_password("wer@example.com") == "geheim"

    def test_nur_der_zeilenumbruch_wird_entfernt(self, monkeypatch, verfuegbar):
        """Leerzeichen koennen Teil des Passworts sein — nur \\n abschneiden."""
        monkeypatch.setattr(
            keychain.subprocess, "run", lambda *a, **k: _ergebnis(0, "  mit raum  \n")
        )
        assert keychain.get_password("wer@example.com") == "  mit raum  "

    def test_kein_eintrag(self, monkeypatch, verfuegbar):
        monkeypatch.setattr(keychain.subprocess, "run", lambda *a, **k: _ergebnis(44, ""))
        assert keychain.get_password("wer@example.com") is None

    def test_leeres_ergebnis_gilt_als_kein_treffer(self, monkeypatch, verfuegbar):
        monkeypatch.setattr(keychain.subprocess, "run", lambda *a, **k: _ergebnis(0, "\n"))
        assert keychain.get_password("wer@example.com") is None

    def test_timeout_bei_gesperrtem_schluesselbund(self, monkeypatch, verfuegbar):
        def wirft(*a, **k):
            raise subprocess.TimeoutExpired(cmd="security", timeout=10)

        monkeypatch.setattr(keychain.subprocess, "run", wirft)
        assert keychain.get_password("wer@example.com") is None

    def test_oserror(self, monkeypatch, verfuegbar):
        def wirft(*a, **k):
            raise OSError("kaputt")

        monkeypatch.setattr(keychain.subprocess, "run", wirft)
        assert keychain.get_password("wer@example.com") is None

    def test_dienstname_wird_uebergeben(self, monkeypatch, verfuegbar):
        gesehen = {}

        def merke(cmd, **k):
            gesehen["cmd"] = cmd
            return _ergebnis(0, "x\n")

        monkeypatch.setattr(keychain.subprocess, "run", merke)
        keychain.get_password("wer@example.com", service="eigener-dienst")
        assert "eigener-dienst" in gesehen["cmd"]
        assert "wer@example.com" in gesehen["cmd"]
        # -w gibt nur das Passwort aus, ohne Metadaten
        assert "-w" in gesehen["cmd"]


@pytest.mark.unit
class TestResolveEmailPassword:
    def test_schluesselbund_hat_vorrang(self, monkeypatch, settings):
        settings.email_username = "wer@example.com"
        settings.email_password = "aus-env"
        monkeypatch.setattr(keychain, "get_password", lambda *a, **k: "aus-keychain")
        assert keychain.resolve_email_password(settings) == "aus-keychain"

    def test_rueckfall_auf_konfiguration(self, monkeypatch, settings):
        settings.email_username = "wer@example.com"
        settings.email_password = "aus-env"
        monkeypatch.setattr(keychain, "get_password", lambda *a, **k: None)
        assert keychain.resolve_email_password(settings) == "aus-env"

    def test_ohne_beides_leer(self, monkeypatch, settings):
        settings.email_username = ""
        settings.email_password = ""
        monkeypatch.setattr(keychain, "get_password", lambda *a, **k: None)
        assert keychain.resolve_email_password(settings) == ""
