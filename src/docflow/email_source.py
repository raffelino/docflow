"""IMAP email source for DocFlow.

Reads emails from a configured IMAP mailbox, extracts PDF/image attachments,
and feeds them through the DocFlow pipeline. Processed emails are moved to a
"Processed" folder (created if needed).

PDF text is extracted directly via pdfplumber. Image attachments are run
through Apple Vision OCR (or the mock fallback).
"""

from __future__ import annotations

import email
import email.policy
import imaplib
import io
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Supported attachment MIME types / extensions
IMAGE_MIMES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/tiff",
    "image/tif",
}
PDF_MIME = "application/pdf"
SUPPORTED_MIMES = IMAGE_MIMES | {PDF_MIME}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif"}
PDF_EXTENSION = ".pdf"


@dataclass
class EmailAttachment:
    filename: str
    content_type: str
    data: bytes
    # email metadata
    subject: str
    sender: str
    email_date: datetime | None
    message_uid: str


@dataclass
class EmailSourceResult:
    attachments: list[EmailAttachment] = field(default_factory=list)
    processed_uids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _parse_email_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def _extract_text_from_pdf(data: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber."""
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        logger.warning("pdfplumber not installed; PDF text extraction skipped")
        return ""

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)


class IMAPEmailSource:
    """Reads and processes email attachments from an IMAP server."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        folder: str = "INBOX",
        processed_folder: str = "DocFlow/Processed",
        subject_filter: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.folder = folder
        self.processed_folder = processed_folder
        self.subject_filter = subject_filter.lower() if subject_filter else ""

    def _connect(self) -> imaplib.IMAP4_SSL:
        conn = imaplib.IMAP4_SSL(self.host, self.port)
        conn.login(self.username, self.password)
        return conn

    def _ensure_processed_folder(self, conn: imaplib.IMAP4_SSL) -> None:
        """Create the processed folder if it doesn't exist."""
        result, _ = conn.create(self.processed_folder)
        # CREATE returns NO if folder already exists — that's fine
        if result not in ("OK", "NO"):
            logger.warning("Could not create processed folder", folder=self.processed_folder)

    def _move_message(self, conn: imaplib.IMAP4_SSL, uid: bytes, destination: str) -> None:
        """Move a message by UID to destination folder (copy + delete + expunge)."""
        conn.uid("COPY", uid, destination)
        conn.uid("STORE", uid, "+FLAGS", r"(\Deleted)")
        conn.expunge()

    def fetch_attachments(self) -> EmailSourceResult:
        """Connect to IMAP and fetch all unprocessed attachments."""
        result = EmailSourceResult()

        try:
            conn = self._connect()
        except Exception as e:
            result.errors.append(f"IMAP connect failed: {e}")
            logger.error("IMAP connect failed", error=str(e))
            return result

        try:
            self._ensure_processed_folder(conn)
            conn.select(self.folder)

            # Search for unseen messages (or all if you want idempotent runs)
            status, data = conn.uid("SEARCH", None, "UNSEEN")
            if status != "OK" or not data[0]:
                logger.info("No unseen messages found", folder=self.folder)
                conn.logout()
                return result

            uids = data[0].split()
            logger.info("Found unseen messages", count=len(uids), folder=self.folder)

            for uid in uids:
                try:
                    self._process_message(conn, uid, result)
                except Exception as e:
                    err = f"Error processing message UID {uid!r}: {e}"
                    logger.error(err)
                    result.errors.append(err)

            # Move processed messages
            for uid_str in result.processed_uids:
                try:
                    self._move_message(conn, uid_str.encode(), self.processed_folder)
                except Exception as e:
                    logger.warning("Could not move message", uid=uid_str, error=str(e))

        finally:
            try:
                conn.logout()
            except Exception:
                pass

        return result

    def _process_message(
        self,
        conn: imaplib.IMAP4_SSL,
        uid: bytes,
        result: EmailSourceResult,
    ) -> None:
        status, msg_data = conn.uid("FETCH", uid, "(RFC822)")
        if status != "OK" or not msg_data or not msg_data[0]:
            return

        raw = msg_data[0][1]  # type: ignore[index]
        msg: EmailMessage = email.message_from_bytes(
            raw,
            policy=email.policy.default,  # type: ignore[arg-type]
        )

        subject = str(msg.get("Subject", ""))
        sender = str(msg.get("From", ""))
        date_str = msg.get("Date")
        email_date = _parse_email_date(date_str)

        # Apply subject filter
        if self.subject_filter and self.subject_filter not in subject.lower():
            return

        attachments_found = False
        for part in msg.walk():
            ct = part.get_content_type().lower()
            filename = part.get_filename()

            if ct in SUPPORTED_MIMES and filename:
                data = part.get_payload(decode=True)
                if data:
                    attachments_found = True
                    result.attachments.append(
                        EmailAttachment(
                            filename=filename,
                            content_type=ct,
                            data=data,
                            subject=subject,
                            sender=sender,
                            email_date=email_date,
                            message_uid=uid.decode(),
                        )
                    )
                    logger.info(
                        "Found attachment",
                        filename=filename,
                        content_type=ct,
                        subject=subject,
                    )
            elif not filename:
                # Try extension-based detection for attachments without explicit MIME
                ext = Path(str(part.get_filename() or "")).suffix.lower()
                if ext in IMAGE_EXTENSIONS or ext == PDF_EXTENSION:
                    data = part.get_payload(decode=True)
                    if data:
                        attachments_found = True
                        fname = part.get_filename() or f"attachment{ext}"
                        result.attachments.append(
                            EmailAttachment(
                                filename=fname,
                                content_type=ct,
                                data=data,
                                subject=subject,
                                sender=sender,
                                email_date=email_date,
                                message_uid=uid.decode(),
                            )
                        )

        if attachments_found:
            result.processed_uids.append(uid.decode())


async def extract_text_from_attachment(attachment: EmailAttachment) -> str:
    """Extract text from an email attachment (OCR for images, pdfplumber for PDFs)."""
    from docflow.ocr import extract_text_from_bytes

    ct = attachment.content_type.lower()
    ext = Path(attachment.filename).suffix.lower()

    if ct == PDF_MIME or ext == PDF_EXTENSION:
        return _extract_text_from_pdf(attachment.data)

    if ct in IMAGE_MIMES or ext in IMAGE_EXTENSIONS:
        return await extract_text_from_bytes(attachment.data, suffix=ext or ".jpg")

    logger.warning(
        "Unsupported attachment type",
        content_type=ct,
        filename=attachment.filename,
    )
    return ""
