"""Unit tests for the OCR module (mocked Vision framework)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from docflow import ocr as ocr_module


@pytest.mark.unit
class TestOCR:
    def test_is_vision_available_returns_bool(self):
        result = ocr_module.is_vision_available()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_extract_text_returns_empty_when_vision_unavailable(self, tmp_dir: Path):
        """When Vision is not available, extract_text returns empty string gracefully."""
        img_path = tmp_dir / "test.jpg"
        img_path.write_bytes(b"fake image data")

        with patch.object(ocr_module, "_VISION_AVAILABLE", False):
            result = await ocr_module.extract_text(img_path)
        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_text_raises_when_file_missing(self, tmp_dir: Path):
        missing = tmp_dir / "nonexistent.jpg"
        with patch.object(ocr_module, "_VISION_AVAILABLE", True):
            with pytest.raises(FileNotFoundError):
                await ocr_module.extract_text(missing)

    @pytest.mark.asyncio
    async def test_extract_text_calls_vision_when_available(self, tmp_dir: Path):
        img_path = tmp_dir / "doc.jpg"
        img_path.write_bytes(b"fake")

        with patch.object(ocr_module, "_VISION_AVAILABLE", True):
            with patch.object(ocr_module, "_run_vision_ocr", return_value="Hello World") as mock_ocr:
                result = await ocr_module.extract_text(img_path)

        assert result == "Hello World"
        mock_ocr.assert_called_once_with(img_path)

    @pytest.mark.asyncio
    async def test_extract_text_from_bytes_no_vision(self, tmp_dir: Path):
        with patch.object(ocr_module, "_VISION_AVAILABLE", False):
            result = await ocr_module.extract_text_from_bytes(b"fake image", suffix=".jpg")
        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_text_from_bytes_with_vision(self):
        with patch.object(ocr_module, "_VISION_AVAILABLE", True):
            with patch.object(ocr_module, "_run_vision_ocr", return_value="Scanned text"):
                result = await ocr_module.extract_text_from_bytes(b"fake image bytes", suffix=".jpg")
        assert result == "Scanned text"
