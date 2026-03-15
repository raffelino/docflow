"""Local filesystem storage backend."""

from __future__ import annotations

import shutil
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


class LocalStorage:
    """Saves documents to a local directory (the default)."""

    name = "local"

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, local_path: Path, destination_path: str) -> str:
        """Copy *local_path* into *base_dir / destination_path*.

        Creates intermediate directories as needed.
        Returns the absolute path of the saved file.
        """
        dest = self.base_dir / destination_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.resolve() != local_path.resolve():
            shutil.copy2(local_path, dest)

        logger.info("Saved document locally", path=str(dest))
        return str(dest)
