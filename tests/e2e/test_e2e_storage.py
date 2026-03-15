"""E2E: local storage, iCloud path, S3 mock (moto)."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image


def _make_pdf(path: Path) -> Path:
    path.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Type /Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
    )
    return path


@pytest.mark.e2e
class TestE2ELocalStorage:
    @pytest.mark.asyncio
    async def test_save_creates_file(self, e2e_dir: Path):
        from docflow.storage.local import LocalStorage

        storage = LocalStorage(base_dir=e2e_dir / "local_output")
        src = _make_pdf(e2e_dir / "source.pdf")

        result = await storage.save(src, "2026/03/invoice.pdf")

        dest = Path(result)
        assert dest.exists()
        assert dest.stat().st_size > 0
        assert dest.name == "invoice.pdf"
        assert "2026/03" in str(dest)

    @pytest.mark.asyncio
    async def test_save_creates_intermediate_dirs(self, e2e_dir: Path):
        from docflow.storage.local import LocalStorage

        storage = LocalStorage(base_dir=e2e_dir / "deep_output")
        src = _make_pdf(e2e_dir / "src2.pdf")

        result = await storage.save(src, "a/b/c/d/file.pdf")
        assert Path(result).exists()

    @pytest.mark.asyncio
    async def test_save_returns_absolute_path(self, e2e_dir: Path):
        from docflow.storage.local import LocalStorage

        storage = LocalStorage(base_dir=e2e_dir / "abs_output")
        src = _make_pdf(e2e_dir / "src3.pdf")

        result = await storage.save(src, "doc.pdf")
        assert Path(result).is_absolute()

    @pytest.mark.asyncio
    async def test_name_property(self, e2e_dir: Path):
        from docflow.storage.local import LocalStorage
        storage = LocalStorage(base_dir=e2e_dir)
        assert storage.name == "local"


@pytest.mark.e2e
class TestE2EICloudStorage:
    @pytest.mark.asyncio
    async def test_save_to_icloud_path(self, e2e_dir: Path):
        """iCloud storage saves to the configured directory (doesn't need real iCloud)."""
        from docflow.storage.icloud import ICloudStorage

        fake_icloud = e2e_dir / "FakeICloud" / "DocFlow"
        storage = ICloudStorage(base_dir=fake_icloud)

        src = _make_pdf(e2e_dir / "src_icloud.pdf")
        result = await storage.save(src, "2026/03/contract.pdf")

        dest = Path(result)
        assert dest.exists()
        assert "FakeICloud" in str(dest)
        assert dest.name == "contract.pdf"

    @pytest.mark.asyncio
    async def test_icloud_creates_dirs(self, e2e_dir: Path):
        from docflow.storage.icloud import ICloudStorage

        base = e2e_dir / "icloud_test"
        storage = ICloudStorage(base_dir=base)
        src = _make_pdf(e2e_dir / "icloud_src.pdf")

        result = await storage.save(src, "deep/nested/doc.pdf")
        assert Path(result).exists()

    def test_name_property(self, e2e_dir: Path):
        from docflow.storage.icloud import ICloudStorage
        storage = ICloudStorage(base_dir=e2e_dir)
        assert storage.name == "icloud"


@pytest.mark.e2e
class TestE2ES3Storage:
    @pytest.mark.asyncio
    async def test_save_to_s3_moto(self, e2e_dir: Path):
        """S3 storage uploads using moto (in-memory S3 mock)."""
        try:
            import boto3
            import moto
        except ImportError:
            pytest.skip("boto3 and moto required for S3 tests")

        from moto import mock_s3
        from docflow.storage.generic_cloud import S3Storage

        with mock_s3():
            import boto3 as _boto3
            conn = _boto3.client("s3", region_name="us-east-1")
            conn.create_bucket(Bucket="test-docflow-bucket")

            storage = S3Storage(
                bucket="test-docflow-bucket",
                prefix="docflow/",
                aws_access_key_id="test",
                aws_secret_access_key="test",
            )
            src = _make_pdf(e2e_dir / "s3_test.pdf")
            result = await storage.save(src, "2026/03/invoice.pdf")

            assert result == "s3://test-docflow-bucket/docflow/2026/03/invoice.pdf"

            # Verify object exists in mocked S3
            resp = conn.get_object(Bucket="test-docflow-bucket", Key="docflow/2026/03/invoice.pdf")
            assert resp["Body"].read()

    def test_s3_raises_without_bucket(self, e2e_dir: Path):
        from docflow.storage.generic_cloud import S3Storage
        with pytest.raises(ValueError, match="S3_BUCKET"):
            S3Storage(bucket="")

    def test_name_property(self, e2e_dir: Path):
        try:
            import boto3
        except ImportError:
            pytest.skip("boto3 required")

        from moto import mock_s3
        from docflow.storage.generic_cloud import S3Storage

        with mock_s3():
            import boto3 as _b
            _b.client("s3", region_name="us-east-1").create_bucket(Bucket="b")
            storage = S3Storage(bucket="b", aws_access_key_id="k", aws_secret_access_key="s")
            assert storage.name == "s3"


@pytest.mark.e2e
class TestE2EStorageFactory:
    def test_get_local_storage(self, e2e_settings):
        from docflow.storage import get_storage_backend
        storage = get_storage_backend(e2e_settings)
        assert storage.name == "local"

    def test_get_icloud_storage(self, e2e_settings, e2e_dir: Path):
        from docflow.storage import get_storage_backend
        settings = e2e_settings.model_copy(
            update={"storage_backend": "icloud", "icloud_docflow_path": e2e_dir / "icloud"}
        )
        storage = get_storage_backend(settings)
        assert storage.name == "icloud"

    def test_invalid_backend_raises(self, e2e_settings):
        from docflow.storage import get_storage_backend
        from unittest.mock import MagicMock

        # Bypass pydantic Literal validation by using a mock settings object
        mock_settings = MagicMock()
        mock_settings.storage_backend = "invalid_backend_xyz"
        mock_settings.output_dir = e2e_settings.output_dir

        with pytest.raises((ValueError, Exception)):
            get_storage_backend(mock_settings)
