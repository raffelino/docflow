"""E2E test fixtures."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from docflow.config import Settings
from docflow.db import Database
from tests.conftest import make_mock_llm


@pytest.fixture
def e2e_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory(prefix="docflow_e2e_") as d:
        yield Path(d)


@pytest.fixture
def e2e_settings(e2e_dir: Path) -> Settings:
    # _env_file=None: die Tests duerfen NICHT von der echten .env abhaengen.
    # Sonst kippen sie, sobald sich dort etwas aendert — bei der Umstellung auf
    # PHOTOS_SOURCE=all sind so drei Scan-State-Tests gebrochen, weil sie
    # ploetzlich den Vollscan-Schluessel bekamen statt den Albumnamen.
    return Settings(
        _env_file=None,
        photos_source="album",
        photos_album="E2EAlbum",
        force_document_albums="Dokumente",
        output_dir=e2e_dir / "output",
        db_path=e2e_dir / "docflow.db",
        llm_provider="anthropic",
        anthropic_api_key="test-key",
        storage_backend="local",
        email_enabled=False,
        schedule_hour=2,
        schedule_minute=0,
    )


@pytest.fixture
def e2e_db(e2e_settings: Settings) -> Database:
    return Database(e2e_settings.db_path)


@pytest.fixture
def e2e_llm():
    return make_mock_llm()


@pytest.fixture
def fake_jpeg(e2e_dir: Path) -> Path:
    from PIL import Image

    path = e2e_dir / "fake_scan.jpg"
    img = Image.new("RGB", (200, 100), color=(240, 240, 240))
    img.save(path, format="JPEG")
    return path
