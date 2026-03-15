"""Apple Vision OCR via pyobjc.

Gracefully degrades when pyobjc is unavailable (non-macOS environments).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

# Try to import pyobjc Vision framework
_VISION_AVAILABLE = False
try:
    import objc  # noqa: F401
    import Quartz  # noqa: F401
    import Vision  # noqa: F401

    _VISION_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning(
        "pyobjc / Vision framework not available — OCR will return empty strings. "
        "Install with: uv sync --extra macos"
    )


def is_vision_available() -> bool:
    return _VISION_AVAILABLE


def _run_vision_ocr(image_path: Path) -> str:
    """Synchronous Vision OCR — must run in a thread (uses ObjC event loop)."""
    import Quartz
    import Vision

    url = Quartz.NSURL.fileURLWithPath_(str(image_path))
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, {})

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)

    success, error = handler.performRequests_error_([request], None)
    if not success or error:
        raise RuntimeError(f"Vision OCR failed: {error}")

    results = request.results()
    if not results:
        return ""

    lines: list[str] = []
    for observation in results:
        candidate = observation.topCandidates_(1)
        if candidate:
            lines.append(str(candidate[0].string()))
    return "\n".join(lines)


async def extract_text(image_path: Path) -> str:
    """Extract text from an image using Apple Vision OCR.

    Returns empty string if Vision is not available.
    """
    if not _VISION_AVAILABLE:
        logger.warning("Vision not available, returning empty OCR text", path=str(image_path))
        return ""

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, _run_vision_ocr, image_path)
    logger.info("OCR complete", path=str(image_path), chars=len(text))
    return text


async def extract_text_from_bytes(image_bytes: bytes, suffix: str = ".jpg") -> str:
    """Extract text from image bytes by writing to a temp file first."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(image_bytes)
        tmp_path = Path(f.name)

    try:
        return await extract_text(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
