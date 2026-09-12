"""Main processing pipeline.

Orchestrates:
  1. Fetching photos from Apple Photos (or email attachments)
  2. OCR via Apple Vision
  3. LLM classification
  4. PDF creation & storage
  5. DB record insertion
"""

from __future__ import annotations

import hashlib
import io
import re
import tempfile
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import structlog
from PIL import Image

from docflow.config import Settings
from docflow.db import Database
from docflow.imaging import ensure_heif_support
from docflow.llm import DocumentClassification, get_llm_provider
from docflow.llm.base import LLMProvider
from docflow.ocr import extract_text
from docflow.photos import PhotoInfo, get_library
from docflow.pre_classifier import classify_media
from docflow.storage import StorageBackend, get_storage_backend

# HEIC muss registriert sein, bevor Pillow das erste Foto oeffnet.
ensure_heif_support()

logger = structlog.get_logger(__name__)


def _safe_filename(name: str) -> str:
    """Strip characters that are unsafe in filenames."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name[:200] or "document.pdf"


MAX_DIMENSION = 2000
JPEG_QUALITY = 85


def _optimize_image(image_path: Path) -> bytes:
    """Resize and compress an image, return optimized JPEG bytes."""
    img = Image.open(image_path)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Resize if larger than MAX_DIMENSION on either side
    w, h = img.size
    if w > MAX_DIMENSION or h > MAX_DIMENSION:
        ratio = min(MAX_DIMENSION / w, MAX_DIMENSION / h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        logger.debug("Image resized", original=f"{w}x{h}", new=f"{new_size[0]}x{new_size[1]}")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def _image_to_pdf_bytes(image_path: Path) -> bytes:
    """Optimize an image and convert to a compact single-page PDF."""
    optimized = _optimize_image(image_path)
    try:
        import img2pdf  # type: ignore

        return img2pdf.convert(io.BytesIO(optimized))
    except Exception:
        img = Image.open(io.BytesIO(optimized))
        buf = io.BytesIO()
        img.save(buf, format="PDF")
        return buf.getvalue()


def _image_bytes_to_pdf_bytes(data: bytes) -> bytes:
    """Convert raw image bytes to an optimized PDF."""
    # Save to temp, optimize, then convert
    img = Image.open(io.BytesIO(data))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    w, h = img.size
    if w > MAX_DIMENSION or h > MAX_DIMENSION:
        ratio = min(MAX_DIMENSION / w, MAX_DIMENSION / h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    opt_buf = io.BytesIO()
    img.save(opt_buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    opt_bytes = opt_buf.getvalue()

    try:
        import img2pdf  # type: ignore

        return img2pdf.convert(io.BytesIO(opt_bytes))
    except Exception:
        out = io.BytesIO()
        Image.open(io.BytesIO(opt_bytes)).save(out, format="PDF")
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
        album_override: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip_cloud_only: bool = False,
    ) -> int:
        """Run the full pipeline. Returns the run_id.

        ``album_override`` waehlt fuer diesen Lauf ein anderes Album; der
        Sonderwert ``"__all__"`` erzwingt einen Vollscan. Ein gesetzter
        Datumsbereich schaltet den inkrementellen Scan ab — der Nutzer definiert
        das Fenster dann selbst.
        """
        run_id = self.db.create_run()
        # Startzeitpunkt als kuenftiger Cutoff: Aufnahmen, die waehrend des Laufs
        # hinzukommen, bleiben so fuer den naechsten Lauf sichtbar.
        run_started = datetime.utcnow()
        log_lines: list[str] = []
        photos_found = 0
        docs_processed = 0
        photos_skipped = 0
        errors = 0

        def log(msg: str) -> None:
            logger.info(msg, run_id=run_id)
            log_lines.append(f"[{datetime.utcnow().isoformat(timespec='seconds')}] {msg}")

        log("Pipeline started")

        # ── 1. Umfang bestimmen ───────────────────────────────────────────────
        scan_all = self.settings.photos_source == "all" or album_override == "__all__"
        if album_override and album_override != "__all__":
            effective_album = album_override
            log(f"Album-Override: '{album_override}' statt '{self.settings.photos_album}'")
        else:
            effective_album = self.settings.photos_album
        album_key = "__all__" if scan_all else effective_album

        if scan_all:
            log("Vollscan der gesamten Photos-Library (Vorpruefung aktiv)")

        # ── 2. Inkrementellen Cutoff bestimmen ────────────────────────────────
        scan_cutoff: datetime | None = None
        if date_from or date_to:
            log(f"Datumsfilter {date_from or '-'} bis {date_to or '-'} "
                f"(Scan-Stand wird ignoriert)")
        else:
            state = self.db.get_scan_state(album_key)
            if state and state.get("last_scanned_at"):
                try:
                    scan_cutoff = datetime.fromisoformat(state["last_scanned_at"])
                    log(f"Inkrementell: nur Aufnahmen seit {scan_cutoff.isoformat()}")
                except ValueError:
                    log(f"Scan-Stand unlesbar ({state['last_scanned_at']!r}) — Erstlauf")
            else:
                log(f"Erstlauf fuer '{album_key}': alle Aufnahmen werden geprueft")

        # ── 3. Aufnahmen durchgehen ───────────────────────────────────────────
        force_albums = {
            a.strip()
            for a in (self.settings.force_document_albums or "").split(",")
            if a.strip()
        }
        photo_iter: Iterator[PhotoInfo] = iter(())
        force_uuids: set[str] = set()
        force_document_all = False
        try:
            library = get_library(album=effective_album, mock_photos=mock_photos)

            # Zaehlen ohne Dateizugriff, damit das Dashboard sofort etwas zeigt
            if scan_all:
                photos_found = library.count_all_photos(
                    date_from=date_from, date_to=date_to, scan_cutoff=scan_cutoff
                )
                log(f"{photos_found} Aufnahmen zu pruefen (gesamte Library)")
            else:
                photos_found = library.count_photos_in_album(
                    effective_album, date_from=date_from, date_to=date_to,
                    scan_cutoff=scan_cutoff,
                )
                log(f"{photos_found} Aufnahmen zu pruefen (Album '{effective_album}')")
            self.db.update_run_progress(run_id, photos_found=photos_found)

            # FORCE_DOCUMENT_ALBUMS: selbst gepflegte Ablagen umgehen die Vorpruefung
            if force_albums:
                if scan_all:
                    force_uuids = library.uuids_in_albums(force_albums)
                    if force_uuids:
                        log(f"{len(force_uuids)} Aufnahmen aus {sorted(force_albums)} "
                            f"gelten ohne Vorpruefung als Dokument")
                elif effective_album.strip().casefold() in {
                    a.casefold() for a in force_albums
                }:
                    force_document_all = True
                    log(f"Album '{effective_album}' ist Dokumentenablage "
                        f"(Vorpruefung uebersprungen)")

            if scan_all:
                photo_iter = library.iter_all_photos(
                    icloud_timeout=self.settings.icloud_download_timeout,
                    date_from=date_from, date_to=date_to,
                    skip_cloud_only=skip_cloud_only, scan_cutoff=scan_cutoff,
                )
            else:
                photo_iter = library.iter_photos_in_album(
                    effective_album,
                    icloud_timeout=self.settings.icloud_download_timeout,
                    date_from=date_from, date_to=date_to,
                    skip_cloud_only=skip_cloud_only, scan_cutoff=scan_cutoff,
                )
        except Exception as e:
            log(f"ERROR fetching photos: {e}")
            errors += 1

        gesehen = 0
        for photo in photo_iter:
            gesehen += 1
            try:
                verarbeitet = await self._process_photo(
                    photo, run_id, log,
                    force_document=force_document_all or photo.uuid in force_uuids,
                )
                if verarbeitet:
                    docs_processed += 1
                else:
                    photos_skipped += 1
            except Exception as e:
                log(f"ERROR processing photo {photo.filename}: {e}")
                errors += 1
            # Zwischenstand: bei einem Vollscan laeuft das lange
            if gesehen % 25 == 0:
                self.db.update_run_progress(
                    run_id, docs_processed=docs_processed, photos_skipped=photos_skipped
                )

        # ── 4. Email ──────────────────────────────────────────────────────────
        if self.settings.email_enabled:
            email_docs, email_errors = await self._process_emails(run_id, log)
            docs_processed += email_docs
            errors += email_errors

        status = "error" if errors and not docs_processed else "success"
        log(f"Pipeline finished — processed: {docs_processed}, "
            f"skipped: {photos_skipped}, errors: {errors}, status: {status}")

        self.db.finish_run(
            run_id=run_id,
            status=status,
            photos_found=photos_found,
            docs_processed=docs_processed,
            errors=errors,
            log="\n".join(log_lines),
            photos_skipped=photos_skipped,
        )

        # ── 5. Scan-Stand fortschreiben ───────────────────────────────────────
        # Nur nach einem erfolgreichen Lauf ohne manuellen Datumsfilter: sonst
        # gelten Aufnahmen als gesehen, die nie geprueft wurden.
        if status == "success" and not (date_from or date_to):
            try:
                self.db.update_scan_state(album_key, run_started, photos_found)
            except Exception as e:
                logger.warning("Scan-Stand nicht gespeichert", album=album_key, error=str(e))

        return run_id

    def _record_skipped(
        self,
        photo: PhotoInfo,
        run_id: int,
        file_hash: str | None,
        media_class: str,
    ) -> None:
        """Uebersprungene Aufnahme vermerken, damit kein Lauf sie erneut OCRt.

        Ohne diesen Eintrag greift der UUID-Dedup beim naechsten Lauf nicht und
        jedes der ~15.900 Fotos wuerde jede Nacht neu durch die Texterkennung
        laufen. Der OCR-Text wird bewusst **nicht** gespeichert: er ist fuer
        aussortierte Aufnahmen wertlos und wuerde die FTS-Tabelle mit
        Zehntausenden Schnipseln fluten.
        """
        name = photo.original_filename or photo.filename
        try:
            self.db.insert_document(
                run_id=run_id,
                original_photo_id=photo.uuid,
                original_filename=name,
                ocr_text="",
                llm_provider=None,
                doc_type="Video" if media_class == "video" else "Foto",
                tags=[],
                suggested_filename=name,
                saved_path=None,
                file_hash=file_hash,
            )
        except Exception as e:  # pragma: no cover - defensiv, darf den Lauf nicht stoppen
            logger.warning(
                "Uebersprungene Aufnahme konnte nicht vermerkt werden",
                filename=name, error=str(e),
            )

    async def _process_photo(
        self,
        photo: PhotoInfo,
        run_id: int,
        log,
        force_document: bool = False,
    ) -> bool:
        """Process a single photo. Returns True if processed, False if skipped."""
        log(f"Processing photo: {photo.filename}")

        # Duplicate check by UUID
        if self.db.document_exists(photo_id=photo.uuid):
            log(f"  SKIP: Already processed (UUID {photo.uuid})")
            return False

        # Videos gar nicht erst anfassen: es gibt keinen OCR-Pfad, und ein
        # Exportversuch loest in Photos.app eine Medienkonvertierung aus, die bei
        # iCloud-only-Videos haengen bleibt.
        if classify_media(photo.filename, None) == "video":
            self._record_skipped(photo, run_id, None, "video")
            log(f"  Skipping video: {photo.filename}")
            return False

        # Check local file
        if not photo.path or not photo.path.exists():
            log(f"  SKIP: No local file for photo {photo.filename} (iCloud download failed?)")
            return False

        # Compute file hash for dedup
        file_hash = hashlib.sha256(photo.path.read_bytes()).hexdigest()
        if self.db.document_exists(file_hash=file_hash):
            log("  SKIP: Already processed (identical file hash)")
            return False

        ocr_text = await extract_text(photo.path)

        log(f"  OCR: {len(ocr_text)} chars extracted")

        # Vorentscheidung: lohnt diese Aufnahme einen LLM-Aufruf?
        media_class = classify_media(
            photo.filename,
            ocr_text,
            min_chars=self.settings.pre_classifier_min_chars,
            force_document=force_document,
        )
        log(f"  Pre-classified as: {media_class}")
        if media_class != "document":
            self._record_skipped(photo, run_id, file_hash, media_class)
            log(f"  Skipping {media_class}: {photo.filename}")
            return False

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

        is_temp_export = str(photo.path).startswith(tempfile.gettempdir())
        try:
            pdf_bytes = _image_to_pdf_bytes(photo.path)
            tmp_path.write_bytes(pdf_bytes)

            # Save via storage backend
            saved_path = await self.storage.save(tmp_path, dest_path)
            log(f"  Saved to: {saved_path}")
        finally:
            tmp_path.unlink(missing_ok=True)
            # Clean up AppleScript-exported temp files
            if is_temp_export:
                photo.path.unlink(missing_ok=True)
                parent = photo.path.parent
                if parent.name.startswith("docflow_export_"):
                    import shutil
                    shutil.rmtree(parent, ignore_errors=True)

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
            file_hash=file_hash,
        )
        return True

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
