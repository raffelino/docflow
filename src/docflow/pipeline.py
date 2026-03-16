"""Main processing pipeline.

Orchestrates:
  1. Fetching photos from Apple Photos (or email attachments)
  2. OCR via Apple Vision
  3. LLM classification
  4. PDF creation & storage
  5. DB record insertion
"""

from __future__ import annotations

import io
import re
import tempfile
from datetime import datetime
from pathlib import Path

import structlog
from PIL import Image

from docflow.config import Settings
from docflow.db import Database
from docflow.llm import DocumentClassification, get_llm_provider
from docflow.llm.base import LLMProvider
from docflow.ocr import extract_text
from docflow.photos import PhotoInfo, get_library
from docflow.storage import StorageBackend, get_storage_backend

logger = structlog.get_logger(__name__)


def _safe_filename(name: str) -> str:
    """Strip characters that are unsafe in filenames."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name[:200] or "document.pdf"


def _image_to_pdf_bytes(image_path: Path) -> bytes:
    """Convert an image file to a single-page PDF in memory."""
    try:
        import img2pdf  # type: ignore

        return img2pdf.convert(str(image_path))
    except Exception:
        # Fallback: use Pillow to save as PDF
        img = Image.open(image_path)
        buf = io.BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buf, format="PDF")
        return buf.getvalue()


def _image_bytes_to_pdf_bytes(data: bytes) -> bytes:
    """Convert raw image bytes to PDF bytes."""
    buf = io.BytesIO(data)
    try:
        import img2pdf  # type: ignore

        return img2pdf.convert(buf)
    except Exception:
        img = Image.open(io.BytesIO(data))
        out = io.BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(out, format="PDF")
        return out.getvalue()


def _destination_path(classification: DocumentClassification, created_at: datetime) -> str:
    """Build a relative destination path like ``2026/03/filename.pdf``."""
    year = created_at.strftime("%Y")
    month = created_at.strftime("%m")
    filename = _safe_filename(classification.suggested_filename)
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    return f"{year}/{month}/{filename}"


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        llm: LLMProvider | None = None,
        storage: StorageBackend | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self.llm: LLMProvider = llm or get_llm_provider(settings)
        self.storage: StorageBackend = storage or get_storage_backend(settings)

    async def run(
        self,
        mock_photos: list[PhotoInfo] | None = None,
    ) -> int:
        """Run the full pipeline. Returns the run_id."""
        run_id = self.db.create_run()
        log_lines: list[str] = []
        photos_found = 0
        docs_processed = 0
        errors = 0

        def log(msg: str) -> None:
            logger.info(msg, run_id=run_id)
            log_lines.append(f"[{datetime.utcnow().isoformat(timespec='seconds')}] {msg}")

        log("Pipeline started")

        # ── 1. Photos ─────────────────────────────────────────────────────────
        try:
            library = get_library(
                album=self.settings.photos_album,
                mock_photos=mock_photos,
            )
            if self.settings.photos_source == "all":
                photos = library.get_all_photos()
                photos_found = len(photos)
                log(f"Found {photos_found} photos in library")
            else:
                photos = library.get_photos_in_album(self.settings.photos_album)
                photos_found = len(photos)
                log(f"Found {photos_found} photos in album '{self.settings.photos_album}'")
        except Exception as e:
            log(f"ERROR fetching photos: {e}")
            errors += 1
            photos = []

        for photo in photos:
            try:
                await self._process_photo(photo, run_id, log)
                docs_processed += 1
            except Exception as e:
                log(f"ERROR processing photo {photo.filename}: {e}")
                errors += 1

        # ── 2. Email ───────────────────────────────────────────────────────────
        if self.settings.email_enabled:
            email_docs, email_errors = await self._process_emails(run_id, log)
            docs_processed += email_docs
            errors += email_errors

        status = "error" if errors and not docs_processed else "success"
        log(f"Pipeline finished — processed: {docs_processed}, errors: {errors}, status: {status}")

        self.db.finish_run(
            run_id=run_id,
            status=status,
            photos_found=photos_found,
            docs_processed=docs_processed,
            errors=errors,
            log="\n".join(log_lines),
        )

        return run_id

    async def _process_photo(
        self,
        photo: PhotoInfo,
        run_id: int,
        log,
    ) -> None:
        log(f"Processing photo: {photo.filename}")

        # OCR
        if photo.path and photo.path.exists():
            ocr_text = await extract_text(photo.path)
        else:
            log(f"  WARNING: No path for photo {photo.filename}, skipping OCR")
            ocr_text = ""

        log(f"  OCR: {len(ocr_text)} chars extracted")

        # LLM classification
        classification = await self.llm.classify_document(ocr_text or "[No text extracted]")
        log(
            f"  Classified as '{classification.doc_type}' "
            f"(confidence={classification.confidence:.2f}, "
            f"filename={classification.suggested_filename})"
        )

        # PDF creation
        created_at = datetime.utcnow()
        dest_path = _destination_path(classification, created_at)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            if photo.path and photo.path.exists():
                pdf_bytes = _image_to_pdf_bytes(photo.path)
            else:
                # Placeholder PDF for photos without a path
                pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"

            tmp_path.write_bytes(pdf_bytes)

            # Save via storage backend
            saved_path = await self.storage.save(tmp_path, dest_path)
            log(f"  Saved to: {saved_path}")
        finally:
            tmp_path.unlink(missing_ok=True)

        # DB
        self.db.insert_document(
            run_id=run_id,
            original_photo_id=photo.uuid,
            original_filename=photo.original_filename,
            ocr_text=ocr_text,
            llm_provider=self.settings.llm_provider,
            doc_type=classification.doc_type,
            tags=classification.tags,
            suggested_filename=classification.suggested_filename,
            saved_path=saved_path,
            source="photos",
            storage_backend=self.storage.name,
        )

    async def _process_emails(self, run_id: int, log) -> tuple[int, int]:
        """Process email attachments. Returns (docs_processed, errors)."""
        from docflow.email_source import IMAPEmailSource, extract_text_from_attachment

        log("Fetching email attachments…")
        source = IMAPEmailSource(
            host=self.settings.email_imap_host,
            port=self.settings.email_imap_port,
            username=self.settings.email_username,
            password=self.settings.email_password,
            folder=self.settings.email_folder,
            processed_folder=self.settings.email_processed_folder,
            subject_filter=self.settings.email_filter_subject,
        )

        result = source.fetch_attachments()
        for err in result.errors:
            log(f"  Email error: {err}")

        docs_processed = 0
        errors = len(result.errors)

        for attachment in result.attachments:
            try:
                log(
                    f"  Processing email attachment: {attachment.filename} "
                    f"(from {attachment.sender}, subject: {attachment.subject!r})"
                )

                ocr_text = await extract_text_from_attachment(attachment)
                log(f"    OCR: {len(ocr_text)} chars")

                classification = await self.llm.classify_document(ocr_text or "[No text extracted]")
                log(
                    f"    Classified as '{classification.doc_type}' "
                    f"(filename={classification.suggested_filename})"
                )

                # PDF — if PDF attachment, use directly; else convert image
                created_at = datetime.utcnow()
                dest_path = _destination_path(classification, created_at)
                ext = Path(attachment.filename).suffix.lower()

                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp_path = Path(tmp.name)

                try:
                    if ext == ".pdf":
                        tmp_path.write_bytes(attachment.data)
                    else:
                        pdf_bytes = _image_bytes_to_pdf_bytes(attachment.data)
                        tmp_path.write_bytes(pdf_bytes)

                    saved_path = await self.storage.save(tmp_path, dest_path)
                    log(f"    Saved to: {saved_path}")
                finally:
                    tmp_path.unlink(missing_ok=True)

                self.db.insert_document(
                    run_id=run_id,
                    original_photo_id=attachment.message_uid,
                    original_filename=attachment.filename,
                    ocr_text=ocr_text,
                    llm_provider=self.settings.llm_provider,
                    doc_type=classification.doc_type,
                    tags=classification.tags,
                    suggested_filename=classification.suggested_filename,
                    saved_path=saved_path,
                    source="email",
                    email_subject=attachment.subject,
                    email_sender=attachment.sender,
                    email_date=attachment.email_date,
                    storage_backend=self.storage.name,
                )
                docs_processed += 1

            except Exception as e:
                log(f"    ERROR processing attachment {attachment.filename}: {e}")
                errors += 1

        log(f"Email: {docs_processed} processed, {errors} errors")
        return docs_processed, errors
