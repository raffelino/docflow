"""Abstract storage backend protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Protocol for document storage backends.

    All backends must implement ``save``, which copies a local file to the
    backend and returns a string representing the canonical storage path
    (filesystem path, S3 URI, etc.).
    """

    @property
    def name(self) -> str:
        """Human-readable backend name, e.g. 'local', 'icloud', 's3'."""
        ...

    async def save(self, local_path: Path, destination_path: str) -> str:
        """Save *local_path* to the backend at *destination_path*.

        Args:
            local_path: Absolute path to the file on the local filesystem.
            destination_path: Relative destination path within the backend
                (e.g. ``"2026/03/invoice.pdf"``).

        Returns:
            The canonical path/URI of the saved file.
        """
        ...
