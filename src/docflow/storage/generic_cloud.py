"""S3-compatible cloud storage backend.

Supports AWS S3 and S3-compatible services (Backblaze B2, MinIO, Cloudflare R2, etc.)
via boto3.

Install with: uv add boto3
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


class S3Storage:
    """Saves documents to an S3 or S3-compatible bucket."""

    name = "s3"

    def __init__(
        self,
        bucket: str,
        prefix: str = "docflow/",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region_name: str = "us-east-1",
    ) -> None:
        if not bucket:
            raise ValueError("S3_BUCKET must be set for the s3 storage backend")

        try:
            import boto3  # type: ignore
        except ImportError as e:
            raise ImportError(
                "boto3 is required for S3 storage. Install with: uv add boto3"
            ) from e

        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/"

        session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )
        self._s3 = session.client(
            "s3",
            endpoint_url=endpoint_url or None,
        )

    def _s3_key(self, destination_path: str) -> str:
        return self.prefix + destination_path.lstrip("/")

    def _s3_uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    async def save(self, local_path: Path, destination_path: str) -> str:
        """Upload *local_path* to S3 at *bucket/prefix/destination_path*.

        Returns the S3 URI (``s3://bucket/key``).
        """
        import asyncio

        key = self._s3_key(destination_path)

        def _upload() -> None:
            self._s3.upload_file(
                str(local_path),
                self.bucket,
                key,
                ExtraArgs={"ContentType": _guess_content_type(local_path)},
            )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _upload)

        uri = self._s3_uri(key)
        logger.info("Uploaded to S3", uri=uri, bucket=self.bucket, key=key)
        return uri


def _guess_content_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }.get(ext, "application/octet-stream")
