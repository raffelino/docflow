"""Vorschaubilder fuer gespeicherte Dokumente.

Die PDFs entstehen aus genau einem Bild (img2pdf bzw. Pillow), das eingebettete
Original laesst sich also mit ``pypdf`` herausholen und verkleinern. Das
vermeidet eine Rasterisierung und damit eine Systemabhaengigkeit wie poppler —
DocFlow soll mit ``uv sync`` vollstaendig einsatzbereit sein.

Ergebnisse werden auf Platte zwischengespeichert. Ohne Cache wuerde eine
Listenansicht mit 50 Eintraegen 50 PDFs oeffnen und 50 Bilder skalieren.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import structlog
from PIL import Image

from docflow.imaging import ensure_heif_support

logger = structlog.get_logger(__name__)

ensure_heif_support()

# 480 px lange Kante — abgelesen am Cache des verlorenen Juni-Codes, dessen
# Dateien noch im Ausgabeordner lagen und durchgaengig diese Groesse hatten.
DEFAULT_MAX_PX = 480
JPEG_QUALITY = 80


def _cache_path(cache_dir: Path, quelle: Path, max_px: int) -> Path:
    """Cache-Name aus Pfad, Groesse und mtime — aendert sich die Datei, faellt
    der alte Eintrag automatisch aus."""
    try:
        stamp = f"{quelle}:{quelle.stat().st_mtime_ns}:{max_px}"
    except OSError:
        stamp = f"{quelle}:{max_px}"
    name = hashlib.sha256(stamp.encode("utf-8")).hexdigest()[:32]
    return cache_dir / f"{name}.jpg"


def _bild_aus_pdf(pdf_path: Path) -> bytes | None:
    """Erstes eingebettetes Bild der ersten Seite."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        if not reader.pages:
            return None
        for bild in reader.pages[0].images:
            if bild.data:
                return bild.data
    except Exception as e:
        logger.debug("Kein Bild aus PDF lesbar", path=str(pdf_path), error=str(e))
    return None


def _verkleinern(roh: bytes, max_px: int) -> bytes | None:
    try:
        geladen = Image.open(io.BytesIO(roh))
        geladen.thumbnail((max_px, max_px))
        # JPEG kann weder Palette noch Alpha — vor dem Speichern umwandeln
        img = geladen if geladen.mode in ("RGB", "L") else geladen.convert("RGB")
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return out.getvalue()
    except Exception as e:
        logger.debug("Verkleinern fehlgeschlagen", error=str(e))
        return None


def render_thumbnail(
    quelle: Path,
    cache_dir: Path | None = None,
    max_px: int = DEFAULT_MAX_PX,
) -> bytes | None:
    """JPEG-Vorschau erzeugen, oder None wenn die Quelle nichts hergibt.

    ``quelle`` darf ein PDF oder direkt ein Bild sein — Email-Anhaenge liegen
    teils als Bild vor.
    """
    if not quelle.exists() or not quelle.is_file():
        return None

    cache_file: Path | None = None
    if cache_dir is not None:
        cache_file = _cache_path(cache_dir, quelle, max_px)
        if cache_file.exists():
            try:
                return cache_file.read_bytes()
            except OSError:
                pass  # neu erzeugen

    if quelle.suffix.lower() == ".pdf":
        roh = _bild_aus_pdf(quelle)
    else:
        try:
            roh = quelle.read_bytes()
        except OSError:
            roh = None
    if not roh:
        return None

    klein = _verkleinern(roh, max_px)
    if klein is None:
        return None

    if cache_file is not None and cache_dir is not None:
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            # Erst daneben schreiben, dann umbenennen: ein abgebrochener
            # Schreibvorgang darf keine halbe Datei im Cache hinterlassen.
            tmp = cache_file.with_suffix(".part")
            tmp.write_bytes(klein)
            tmp.replace(cache_file)
        except OSError as e:
            logger.debug("Cache nicht beschreibbar", error=str(e))

    return klein
