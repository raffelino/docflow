"""Zugangsdaten aus dem macOS-Schluesselbund lesen.

Das Email-Passwort im Klartext in ``.env`` zu halten ist zwei Mal unangenehm:
die Datei liegt unverschluesselt neben dem Code, und die E2E-Tests schreiben
``.env`` neu — ein dort eingetragenes Passwort ueberlebt einen Testlauf nicht
zwangslaeufig. Der Schluesselbund loest beides.

Ablegen (einmalig, interaktiv):

    security add-generic-password -s docflow-email -a <benutzer> -w

Gelesen wird ueber ``security find-generic-password``. Ist kein Eintrag
vorhanden oder laeuft DocFlow nicht auf macOS, gilt weiterhin ``EMAIL_PASSWORD``
aus der Konfiguration.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from docflow.config import Settings

logger = structlog.get_logger(__name__)

DEFAULT_SERVICE = "docflow-email"

# Der Aufruf ist nicht interaktiv, solange der Schluesselbund entsperrt ist.
# Bleibt er gesperrt, fragt macOS grafisch nach — in einem Hintergrunddienst
# wuerde das haengen, deshalb ein knappes Zeitbudget.
_TIMEOUT_SECONDS = 10


def is_available() -> bool:
    """True, wenn das ``security``-Werkzeug nutzbar ist (also auf macOS)."""
    return sys.platform == "darwin" and shutil.which("security") is not None


def get_password(account: str, service: str = DEFAULT_SERVICE) -> str | None:
    """Passwort aus dem Schluesselbund holen, oder None.

    Kein Fehlerfall ist hier fatal: fehlt der Eintrag, faellt der Aufrufer auf
    die Konfiguration zurueck.
    """
    if not account:
        return None
    if not is_available():
        return None

    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "Schluesselbund antwortet nicht — ist er gesperrt?",
            service=service, account=account,
        )
        return None
    except OSError as e:
        logger.warning("Schluesselbund nicht erreichbar", error=str(e))
        return None

    if result.returncode != 0:
        # Kein Eintrag gefunden ist der Normalfall, wenn niemand einen angelegt hat.
        logger.debug(
            "Kein Schluesselbund-Eintrag gefunden",
            service=service, account=account, returncode=result.returncode,
        )
        return None

    # -w gibt das Passwort mit abschliessendem Zeilenumbruch aus. Nur diesen
    # entfernen: fuehrende oder nachgestellte Leerzeichen koennen Teil des
    # Passworts sein.
    password = result.stdout.removesuffix("\n")
    return password or None


def resolve_email_password(settings: Settings) -> str:
    """Email-Passwort bestimmen: Schluesselbund zuerst, dann Konfiguration."""
    aus_keychain = get_password(settings.email_username)
    if aus_keychain:
        logger.info(
            "Email-Passwort aus dem Schluesselbund", account=settings.email_username
        )
        return aus_keychain
    if settings.email_password:
        logger.debug("Email-Passwort aus der Konfiguration")
    return settings.email_password
