"""Apple Photos integration via osxphotos.

Gracefully degrades when osxphotos is unavailable (non-macOS environments).

## Warum Generatoren

Bei ``PHOTOS_SOURCE=all`` geht die Pipeline ueber ~15.900 Aufnahmen. Eine Liste
aufzubauen heisst, vorher jede einzelne anzufassen — bei iCloud-only-Fotos also
Zehntausende Sekunden Download, bevor das erste Dokument verarbeitet ist. Die
``iter_*``-Methoden liefern stattdessen lazy und filtern so fruehe wie moeglich:
Datumsbereich, Scan-Cutoff und Videoformat werden **vor** jedem Dateizugriff
geprueft.

## Warum kein Export mehr fuer lokale HEIC-Dateien

Frueher wurde jede HEIC-Datei per AppleScript nach JPEG exportiert, weil Pillow
HEIC nicht lesen konnte. Dieser Export haengt bei iCloud-Fotos regelmaessig im
60-Sekunden-Timeout. Seit ``pillow-heif`` eine echte Abhaengigkeit ist (siehe
``imaging.py``) liest Pillow HEIC direkt — exportiert wird nur noch, was gar
nicht lokal vorliegt.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import structlog

from docflow.pre_classifier import is_video

logger = structlog.get_logger(__name__)

_OSXPHOTOS_AVAILABLE = False
try:
    import osxphotos  # noqa: F401

    _OSXPHOTOS_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning(
        "osxphotos not available. Install with: uv sync --extra macos"
    )

_EXPORT_PREFIX = "docflow_export_"


def is_osxphotos_available() -> bool:
    return _OSXPHOTOS_AVAILABLE


def _utc_naive(dt: datetime) -> datetime:
    """Auf naives UTC bringen, damit tz-aware und naiv vergleichbar sind."""
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _added_before_cutoff(date_added: datetime | None, cutoff: datetime | None) -> bool:
    """True, wenn die Aufnahme vor dem Cutoff des inkrementellen Scans hinzukam.

    osxphotos liefert ``date_added`` tz-aware, der Scan-State speichert naives
    UTC. Ein direkter Vergleich wirft deshalb ``TypeError`` — beide Seiten werden
    hier normalisiert. Fehlt eine der Angaben, wird nichts uebersprungen: im
    Zweifel lieber einmal zu viel pruefen als ein Dokument verlieren.
    """
    if date_added is None or cutoff is None:
        return False
    return _utc_naive(date_added) < _utc_naive(cutoff)


@dataclass
class PhotoInfo:
    """Minimal photo metadata for pipeline use."""

    uuid: str
    filename: str
    path: Path | None
    original_filename: str
    # Aufnahmedatum (fuer Ablage und Datumsfilter)
    date: datetime | None = field(default=None)
    photo_date: datetime | None = field(default=None)
    # Zeitpunkt der Aufnahme in die Library — Grundlage des inkrementellen Scans
    date_added: datetime | None = field(default=None)


class PhotosLibrary:
    """Interface to Apple Photos library."""

    def __init__(self, db_path: str | None = None) -> None:
        if not _OSXPHOTOS_AVAILABLE:
            raise RuntimeError("osxphotos is not installed. Run: uv sync --extra macos")
        import osxphotos

        self._lib = osxphotos.PhotosDB(dbfile=db_path) if db_path else osxphotos.PhotosDB()
        logger.info("Photos library opened")

    # ── Auswahl ──────────────────────────────────────────────────────────────

    def _find_album(self, album_name: str):
        for album in self._lib.album_info:
            if album.title == album_name:
                return album
        logger.warning("Album not found", album=album_name)
        return None

    @staticmethod
    def _matches_date_range(p, date_from: date | None, date_to: date | None) -> bool:
        """Aufnahmedatum gegen den optionalen Filter pruefen (ohne Dateizugriff)."""
        if date_from is None and date_to is None:
            return True
        taken = getattr(p, "date", None)
        if taken is None:
            # Ohne Datum nicht ausschliessen — sonst verschwinden Aufnahmen
            # stillschweigend aus jedem gefilterten Lauf.
            return True
        taken_day = _utc_naive(taken).date()
        if date_from and taken_day < date_from:
            return False
        if date_to and taken_day > date_to:
            return False
        return True

    def _select(
        self,
        photos: Iterator,
        date_from: date | None,
        date_to: date | None,
        scan_cutoff: datetime | None,
    ) -> Generator:
        """Alle Filter, die ohne Dateizugriff entschieden werden koennen."""
        for p in photos:
            if not self._matches_date_range(p, date_from, date_to):
                continue
            if _added_before_cutoff(getattr(p, "date_added", None), scan_cutoff):
                continue
            yield p

    def uuids_in_albums(self, album_names: set[str]) -> set[str]:
        """UUIDs aller Aufnahmen in den genannten Alben (Titelvergleich ohne Gross/Klein).

        Wird fuer FORCE_DOCUMENT_ALBUMS beim Vollscan gebraucht: dort kommen die
        Aufnahmen nicht albumweise, die Zugehoerigkeit muss also vorab bekannt sein.
        """
        if not album_names:
            return set()
        gesucht = {n.strip().casefold() for n in album_names if n.strip()}
        treffer: set[str] = set()
        for album in self._lib.album_info:
            if (album.title or "").casefold() in gesucht:
                treffer.update(p.uuid for p in album.photos)
        return treffer

    # ── Zaehlen (ohne Export) ────────────────────────────────────────────────

    def count_photos_in_album(
        self,
        album_name: str,
        date_from: date | None = None,
        date_to: date | None = None,
        scan_cutoff: datetime | None = None,
    ) -> int:
        """Anzahl passender Aufnahmen, ohne eine einzige Datei anzufassen."""
        target = self._find_album(album_name)
        if target is None:
            return 0
        return sum(1 for _ in self._select(iter(target.photos), date_from, date_to, scan_cutoff))

    def count_all_photos(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        scan_cutoff: datetime | None = None,
    ) -> int:
        return sum(1 for _ in self._select(iter(self._lib.photos()), date_from, date_to, scan_cutoff))

    # ── Einzelne Aufnahme ────────────────────────────────────────────────────

    @staticmethod
    def _local_path(p) -> Path | None:
        """Lokal vorhandene Datei, HEIC eingeschlossen (Pillow liest sie direkt)."""
        for candidate in (getattr(p, "path", None), getattr(p, "path_edited", None)):
            if candidate:
                path = Path(candidate)
                if path.exists():
                    return path
        return None

    @staticmethod
    def _download_from_icloud(p, timeout: int) -> Path | None:
        """iCloud-only-Aufnahme ueber Photos.app in ein Temp-Verzeichnis holen.

        Nutzt ``osxphotos.PhotoInfo.export`` mit ``use_photos_export``: der
        frueher verwendete AppleScript-Aufruf blieb bei iCloud-Fotos regelmaessig
        haengen, bis das Timeout griff.
        """
        export_dir = Path(tempfile.mkdtemp(prefix=_EXPORT_PREFIX))
        try:
            exported = p.export(
                str(export_dir),
                use_photos_export=True,
                timeout=timeout,
                overwrite=True,
            )
            for item in exported or []:
                path = Path(item)
                if path.exists():
                    logger.info("Foto von iCloud geladen", uuid=p.uuid, path=str(path))
                    return path
            logger.warning("iCloud-Export lieferte keine Datei", uuid=p.uuid)
        except Exception as e:
            logger.warning("iCloud-Export fehlgeschlagen", uuid=p.uuid, error=str(e))
        shutil.rmtree(export_dir, ignore_errors=True)
        return None

    def _to_photo_info(self, p, path: Path | None) -> PhotoInfo:
        taken = getattr(p, "date", None)
        return PhotoInfo(
            uuid=p.uuid,
            filename=p.filename,
            path=path,
            original_filename=p.original_filename or p.filename,
            date=taken,
            photo_date=taken,
            date_added=getattr(p, "date_added", None),
        )

    def _resolve(self, p, icloud_timeout: int, skip_cloud_only: bool) -> PhotoInfo:
        """PhotoInfo mit nutzbarem Pfad — laedt nur, was noetig und erlaubt ist."""
        # Videos nie anfassen: es gibt keinen OCR-Pfad, und ein Exportversuch
        # loest in Photos.app eine Medienkonvertierung aus, die haengen bleibt.
        if is_video(p.filename):
            return self._to_photo_info(p, None)

        local = self._local_path(p)
        if local is not None:
            return self._to_photo_info(p, local)

        if skip_cloud_only or not getattr(p, "ismissing", False):
            # Kein lokaler Pfad und kein Download erlaubt (oder Photos meldet die
            # Datei als vorhanden, obwohl sie fehlt) -> ohne Pfad weitergeben.
            return self._to_photo_info(p, None)

        logger.info("Lade Foto von iCloud", filename=p.filename, uuid=p.uuid)
        return self._to_photo_info(p, self._download_from_icloud(p, icloud_timeout))

    # ── Iteratoren ───────────────────────────────────────────────────────────

    def iter_photos_in_album(
        self,
        album_name: str,
        icloud_timeout: int = 300,
        date_from: date | None = None,
        date_to: date | None = None,
        skip_cloud_only: bool = False,
        scan_cutoff: datetime | None = None,
    ) -> Generator[PhotoInfo, None, None]:
        """Aufnahmen des Albums einzeln liefern, Dateizugriff erst beim Yield."""
        target = self._find_album(album_name)
        if target is None:
            return
        for p in self._select(iter(target.photos), date_from, date_to, scan_cutoff):
            yield self._resolve(p, icloud_timeout, skip_cloud_only)

    def iter_all_photos(
        self,
        icloud_timeout: int = 300,
        date_from: date | None = None,
        date_to: date | None = None,
        skip_cloud_only: bool = False,
        scan_cutoff: datetime | None = None,
    ) -> Generator[PhotoInfo, None, None]:
        """Wie ``iter_photos_in_album``, aber ueber die gesamte Library."""
        for p in self._select(iter(self._lib.photos()), date_from, date_to, scan_cutoff):
            yield self._resolve(p, icloud_timeout, skip_cloud_only)

    # ── Rueckwaertskompatibel ────────────────────────────────────────────────

    def get_photos_in_album(self, album_name: str) -> list[PhotoInfo]:
        """Eager-Variante. Fuer grosse Mengen ``iter_photos_in_album`` nutzen."""
        return list(self.iter_photos_in_album(album_name))

    def get_all_photos(self) -> list[PhotoInfo]:
        """Eager-Variante. Fuer die ganze Library ``iter_all_photos`` nutzen."""
        return list(self.iter_all_photos())


def cleanup_temp_export(path: Path | None) -> None:
    """Temporaeren iCloud-Export samt Verzeichnis entfernen.

    Nur Pfade unterhalb des System-Temp-Verzeichnisses mit unserem Praefix
    werden angefasst — die Originale in der Photos-Library darf das nie treffen.
    """
    if path is None:
        return
    parent = path.parent
    if not parent.name.startswith(_EXPORT_PREFIX):
        return
    if not str(parent).startswith(tempfile.gettempdir()):
        return
    shutil.rmtree(parent, ignore_errors=True)


class MockPhotosLibrary:
    """In-memory mock for testing without Apple Photos."""

    def __init__(self, photos: list[PhotoInfo] | None = None) -> None:
        self._photos: list[PhotoInfo] = photos or []

    def add_photo(self, photo: PhotoInfo) -> None:
        self._photos.append(photo)

    @staticmethod
    def _matches_date_range(photo: PhotoInfo, date_from: date | None, date_to: date | None) -> bool:
        if date_from is None and date_to is None:
            return True
        taken = photo.photo_date or photo.date
        if taken is None:
            return True
        taken_day = _utc_naive(taken).date()
        if date_from and taken_day < date_from:
            return False
        if date_to and taken_day > date_to:
            return False
        return True

    def _select(
        self,
        date_from: date | None,
        date_to: date | None,
        scan_cutoff: datetime | None,
    ) -> Generator[PhotoInfo, None, None]:
        for photo in self._photos:
            if not self._matches_date_range(photo, date_from, date_to):
                continue
            if _added_before_cutoff(photo.date_added, scan_cutoff):
                continue
            yield photo

    def iter_photos_in_album(
        self,
        album_name: str,
        icloud_timeout: int = 300,
        date_from: date | None = None,
        date_to: date | None = None,
        skip_cloud_only: bool = False,
        scan_cutoff: datetime | None = None,
    ) -> Generator[PhotoInfo, None, None]:
        yield from self._select(date_from, date_to, scan_cutoff)

    def iter_all_photos(
        self,
        icloud_timeout: int = 300,
        date_from: date | None = None,
        date_to: date | None = None,
        skip_cloud_only: bool = False,
        scan_cutoff: datetime | None = None,
    ) -> Generator[PhotoInfo, None, None]:
        yield from self.iter_photos_in_album(
            "",
            icloud_timeout=icloud_timeout,
            date_from=date_from,
            date_to=date_to,
            skip_cloud_only=skip_cloud_only,
            scan_cutoff=scan_cutoff,
        )

    def count_photos_in_album(
        self,
        album_name: str,
        date_from: date | None = None,
        date_to: date | None = None,
        scan_cutoff: datetime | None = None,
    ) -> int:
        return sum(1 for _ in self._select(date_from, date_to, scan_cutoff))

    def count_all_photos(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        scan_cutoff: datetime | None = None,
    ) -> int:
        return self.count_photos_in_album("", date_from=date_from, date_to=date_to,
                                          scan_cutoff=scan_cutoff)

    def uuids_in_albums(self, album_names: set[str]) -> set[str]:
        # Der Mock kennt nur ein Album; sind Namen genannt, gehoert alles dazu.
        if not {n.strip() for n in album_names if n.strip()}:
            return set()
        return {p.uuid for p in self._photos}

    def get_photos_in_album(self, album_name: str) -> list[PhotoInfo]:
        return list(self._photos)

    def get_all_photos(self) -> list[PhotoInfo]:
        return list(self._photos)


def get_library(
    album: str,
    mock_photos: list[PhotoInfo] | None = None,
    db_path: str | None = None,
) -> PhotosLibrary | MockPhotosLibrary:
    """Return a real or mock Photos library depending on availability."""
    if mock_photos is not None:
        return MockPhotosLibrary(mock_photos)
    if _OSXPHOTOS_AVAILABLE:
        return PhotosLibrary(db_path=db_path)
    raise RuntimeError("osxphotos not available. Use mock_photos for testing.")
