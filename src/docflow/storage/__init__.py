"""Storage backend factory."""

from __future__ import annotations

from docflow.config import Settings
from docflow.storage.base import StorageBackend


def get_storage_backend(settings: Settings) -> StorageBackend:
    """Return the configured storage backend."""
    backend = settings.storage_backend

    if backend == "local":
        from docflow.storage.local import LocalStorage

        return LocalStorage(base_dir=settings.output_dir)

    elif backend == "icloud":
        from docflow.storage.icloud import ICloudStorage

        return ICloudStorage(base_dir=settings.icloud_docflow_path)

    elif backend == "s3":
        from docflow.storage.generic_cloud import S3Storage

        return S3Storage(
            bucket=settings.s3_bucket,
            prefix=settings.s3_prefix,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            endpoint_url=settings.s3_endpoint_url or None,
        )

    else:
        raise ValueError(f"Unknown storage backend: {backend!r}")


__all__ = ["StorageBackend", "get_storage_backend"]
