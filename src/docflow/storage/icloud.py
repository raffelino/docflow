"""iCloud Drive storage backend.

iCloud Drive is accessible as a regular filesystem path on macOS:
    ~/Library/Mobile Documents/com~apple~CloudDocs/

Files copied there are automatically synced by the iCloud daemon
(bird / cloudd). No SDK or API key needed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_ICLOUD_BASE = Path(
    "~/Library/Mobile Documents/com~apple~CloudDocs/DocFlow"
).expanduser()


class ICloudStorage:
    """Saves documents into iCloud Drive (synced automatically by macOS)."""

    name = "icloud"

    def __init__(self, base_dir: Path = DEFAULT_ICLOUD_BASE) -> None:
        self.base_dir = base_dir.expanduser().resolve()

    async def save(self, local_path: Path, destination_path: str) -> str:
        """Copy *local_path* into the iCloud DocFlow folder.

        iCloud will pick up the file automatically and sync it.
        Returns the absolute filesystem path (which is also the iCloud path).
        """
        self.base_dir.mkdir(parents=True, exist_ok=True)
        dest = self.base_dir / destination_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.resolve() != local_path.resolve():
            shutil.copy2(local_path, dest)

        logger.info("Saved document to iCloud Drive", path=str(dest))
        return str(dest)

    @property
    def is_available(self) -> bool:
        """True if the iCloud Drive path exists (i.e. running on macOS with iCloud)."""
        return self.base_dir.parent.exists()
