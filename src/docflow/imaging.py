"""Bildformat-Unterstuetzung, die vor jedem Pillow-Zugriff stehen muss.

iPhone-Fotos sind HEIC. Ohne registrierten HEIF-Opener scheitert jedes
``Image.open`` darauf mit ``cannot identify image file`` — und weil das eine
gewoehnliche ``UnidentifiedImageError`` ist, sieht es im Log wie ein
unlesbares Foto aus statt wie eine fehlende Abhaengigkeit. Genau diese
Verwechslung hat HEIC-Dokumente frueher als Fotos aussortiert.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

_registered = False
_available: bool | None = None


def ensure_heif_support() -> bool:
    """Registriert den HEIF-Opener in Pillow. Idempotent.

    Gibt zurueck, ob HEIC gelesen werden kann. Fehlt ``pillow-heif``, wird das
    einmal als Warnung geloggt, statt spaeter pro Datei zu scheitern.
    """
    global _registered, _available
    if _registered:
        return bool(_available)

    _registered = True
    try:
        from pillow_heif import register_heif_opener
    except ImportError:
        _available = False
        logger.warning(
            "pillow-heif fehlt — HEIC-Dateien koennen nicht gelesen werden "
            "(OCR liefert leeren Text, Dokumente werden als Fotos aussortiert). "
            "Behebung: uv sync",
        )
        return False

    register_heif_opener()
    _available = True
    logger.debug("HEIF-Opener registriert")
    return True


def heif_available() -> bool:
    """True, wenn HEIC-Unterstuetzung aktiv ist (registriert bei Bedarf)."""
    return ensure_heif_support()
