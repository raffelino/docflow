"""Apple Photos integration via osxphotos.

Gracefully degrades when osxphotos is unavailable (non-macOS environments).
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

_OSXPHOTOS_AVAILABLE = False
try:
    import osxphotos  # noqa: F401

    _OSXPHOTOS_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning(
        "osxphotos not available. Install with: uv sync --extra macos"
    )


def is_osxphotos_available() -> bool:
    return _OSXPHOTOS_AVAILABLE


@dataclass
class PhotoInfo:
    """Minimal photo metadata for pipeline use."""

    uuid: str
    filename: str
    path: Path | None
    original_filename: str


class PhotosLibrary:
    """Interface to Apple Photos library."""

    def __init__(self, db_path: str | None = None) -> None:
        if not _OSXPHOTOS_AVAILABLE:
            raise RuntimeError("osxphotos is not installed. Run: uv sync --extra macos")
        import osxphotos

        self._lib = osxphotos.PhotosDB(dbfile=db_path) if db_path else osxphotos.PhotosDB()
        logger.info("Photos library opened")

    def _to_photo_info(self, p) -> PhotoInfo:
        """Convert an osxphotos photo object to PhotoInfo.

        Always exports via AppleScript to get a universally readable JPEG,
        avoiding HEIC compatibility issues with Pillow/img2pdf.
        Falls back to the local path only for non-HEIC formats that exist locally.
        """
        path: Path | None = None

        # Try local path for non-HEIC files first
        local_path = Path(p.path) if p.path else (Path(p.path_edited) if p.path_edited else None)
        if local_path and local_path.exists() and local_path.suffix.lower() not in (".heic", ".heif"):
            path = local_path
        else:
            # Export via AppleScript (converts HEIC to JPEG, downloads from iCloud)
            path = self._export_cloud_photo(p)

        return PhotoInfo(
            uuid=p.uuid,
            filename=p.filename,
            path=path,
            original_filename=p.original_filename or p.filename,
        )

    @staticmethod
    def _export_cloud_photo(photo) -> Path | None:
        """Export an iCloud-only photo via Photos.app AppleScript."""
        try:
            export_dir = Path(tempfile.mkdtemp(prefix="docflow_export_"))
            script = (
                'tell application "Photos"\n'
                f'  set thePhoto to media item id "{photo.uuid}"\n'
                f'  set thePath to POSIX file "{export_dir}"\n'
                "  export {thePhoto} to thePath\n"
                "end tell"
            )
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                logger.warning(
                    "AppleScript export failed",
                    uuid=photo.uuid,
                    stderr=result.stderr.strip(),
                )
                return None

            exported = list(export_dir.iterdir())
            if exported:
                logger.info(
                    "Exported iCloud photo",
                    uuid=photo.uuid,
                    path=str(exported[0]),
                )
                return exported[0]
        except Exception as e:
            logger.warning("Cloud photo export error", uuid=photo.uuid, error=str(e))
        return None

    def get_photos_in_album(self, album_name: str) -> list[PhotoInfo]:
        """Return all photos in the named album."""
        albums = self._lib.album_info
        target = None
        for album in albums:
            if album.title == album_name:
                target = album
                break

        if target is None:
            logger.warning("Album not found", album=album_name)
            return []

        result = [self._to_photo_info(p) for p in target.photos]
        logger.info("Found photos in album", album=album_name, count=len(result))
        return result

    def get_all_photos(self) -> list[PhotoInfo]:
        """Return all photos in the library."""
        result = [self._to_photo_info(p) for p in self._lib.photos()]
        logger.info("Found photos in library", count=len(result))
        return result


class MockPhotosLibrary:
    """In-memory mock for testing without Apple Photos."""

    def __init__(self, photos: list[PhotoInfo] | None = None) -> None:
        self._photos: list[PhotoInfo] = photos or []

    def add_photo(self, photo: PhotoInfo) -> None:
        self._photos.append(photo)

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
