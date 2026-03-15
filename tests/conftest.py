"""Shared pytest fixtures and markers."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from docflow.config import Settings
from docflow.db import Database
from docflow.llm.base import DocumentClassification
from docflow.photos import PhotoInfo


# ── Markers ───────────────────────────────────────────────────────────────────


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: fast unit tests (no I/O, no network)")
    config.addinivalue_line("markers", "e2e: end-to-end tests (real SQLite, real files, mocked external APIs)")


# ── Helpers ───────────────────────────────────────────────────────────────────


FAKE_CLASSIFICATION = DocumentClassification(
    doc_type="Rechnung",
    tags=["Vodafone", "2026-03", "Telekommunikation"],
    suggested_filename="2026-03_Vodafone_Rechnung.pdf",
    confidence=0.95,
)


def make_mock_llm(classification: DocumentClassification = FAKE_CLASSIFICATION):
    """Return a mock LLM provider."""
    llm = MagicMock()
    llm.classify_document = AsyncMock(return_value=classification)
    return llm


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def db(tmp_dir: Path) -> Database:
    return Database(tmp_dir / "test.db")


@pytest.fixture
def settings(tmp_dir: Path) -> Settings:
    return Settings(
        photos_album="TestAlbum",
        output_dir=tmp_dir / "output",
        db_path=tmp_dir / "docflow.db",
        llm_provider="anthropic",
        anthropic_api_key="test-key",
        storage_backend="local",
        email_enabled=False,
        web_host="127.0.0.1",
        web_port=8765,
    )


@pytest.fixture
def mock_llm():
    return make_mock_llm()


@pytest.fixture
def fake_image(tmp_dir: Path) -> Path:
    """Create a tiny JPEG-like image file for testing."""
    from PIL import Image

    path = tmp_dir / "test_doc.jpg"
    img = Image.new("RGB", (100, 50), color=(255, 255, 255))
    img.save(path, format="JPEG")
    return path


@pytest.fixture
def fake_photo(fake_image: Path) -> PhotoInfo:
    return PhotoInfo(
        uuid="test-uuid-001",
        filename="test_doc.jpg",
        path=fake_image,
        original_filename="scan_001.jpg",
    )
