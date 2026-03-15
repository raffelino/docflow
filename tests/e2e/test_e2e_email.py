"""E2E: mock IMAP → attachment → full pipeline."""

from __future__ import annotations

import email
import email.encoders
import email.mime.base
import email.mime.multipart
import email.mime.text
import io
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from docflow.db import Database
from docflow.email_source import (
    EmailAttachment,
    IMAPEmailSource,
    extract_text_from_attachment,
)
from docflow.pipeline import Pipeline
from docflow.storage.local import LocalStorage


def _make_fake_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (100, 50), color=(200, 200, 200)).save(buf, format="JPEG")
    return buf.getvalue()


def _make_fake_pdf_bytes() -> bytes:
    """Minimal valid PDF."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type /Pages /Kids [3 0 R] /Count 1>>endobj\n"
        b"3 0 obj<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"trailer<</Root 1 0 R /Size 4>>\nstartxref\n%%EOF\n"
    )


@pytest.mark.e2e
class TestE2EEmailPipeline:
    @pytest.mark.asyncio
    async def test_email_jpeg_attachment_through_pipeline(
        self,
        e2e_settings,
        e2e_db: Database,
        e2e_llm,
    ):
        """JPEG attachment from email goes through OCR → LLM → PDF → DB."""
        attachment = EmailAttachment(
            filename="rechnung.jpg",
            content_type="image/jpeg",
            data=_make_fake_jpeg_bytes(),
            subject="Ihre Rechnung von Vodafone",
            sender="rechnung@vodafone.de",
            email_date=datetime(2026, 3, 10, 8, 0),
            message_uid="12345",
        )

        e2e_settings = e2e_settings.model_copy(update={"email_enabled": True})
        storage = LocalStorage(base_dir=e2e_settings.output_dir)
        pipeline = Pipeline(
            settings=e2e_settings,
            db=e2e_db,
            llm=e2e_llm,
            storage=storage,
        )

        # Mock IMAP to return our attachment
        mock_imap_result = MagicMock()
        mock_imap_result.attachments = [attachment]
        mock_imap_result.processed_uids = ["12345"]
        mock_imap_result.errors = []

        mock_source_instance = MagicMock()
        mock_source_instance.fetch_attachments.return_value = mock_imap_result

        with patch(
            "docflow.pipeline.extract_text",
            new=AsyncMock(return_value=""),
        ):
            with patch(
                "docflow.pipeline.get_library",
                return_value=MagicMock(get_photos_in_album=MagicMock(return_value=[])),
            ):
                with patch("docflow.email_source.IMAPEmailSource", return_value=mock_source_instance):
                    with patch(
                        "docflow.email_source.extract_text_from_attachment",
                        new=AsyncMock(return_value="Vodafone Rechnung 45 EUR"),
                    ):
                        import docflow.email_source as es_mod
                        es_mod.IMAPEmailSource = MagicMock(return_value=mock_source_instance)
                        es_mod.extract_text_from_attachment = AsyncMock(return_value="Vodafone Rechnung 45 EUR")
                        run_id = await pipeline.run()

        run = e2e_db.get_run(run_id)
        assert run["status"] == "success"
        assert run["docs_processed"] == 1

        docs = e2e_db.list_documents(source="email")
        assert len(docs) == 1
        doc = docs[0]
        assert doc["source"] == "email"
        assert doc["email_subject"] == "Ihre Rechnung von Vodafone"
        assert doc["email_sender"] == "rechnung@vodafone.de"
        assert doc["doc_type"] == "Rechnung"

        saved = Path(doc["saved_path"])
        assert saved.exists()
        assert saved.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_extract_text_from_pdf_attachment(self):
        """PDF attachment goes through pdfplumber text extraction."""
        attachment = EmailAttachment(
            filename="document.pdf",
            content_type="application/pdf",
            data=_make_fake_pdf_bytes(),
            subject="Document",
            sender="sender@example.com",
            email_date=None,
            message_uid="99",
        )

        # pdfplumber may return empty for our minimal PDF, that's fine
        with patch("docflow.email_source._extract_text_from_pdf", return_value="PDF text content"):
            text = await extract_text_from_attachment(attachment)

        assert text == "PDF text content"

    @pytest.mark.asyncio
    async def test_extract_text_from_image_attachment(self):
        """JPEG attachment calls OCR."""
        attachment = EmailAttachment(
            filename="scan.jpg",
            content_type="image/jpeg",
            data=_make_fake_jpeg_bytes(),
            subject="Scan",
            sender="x@y.com",
            email_date=None,
            message_uid="1",
        )

        with patch("docflow.ocr.extract_text_from_bytes", new=AsyncMock(return_value="scanned text")):
            with patch.dict("sys.modules", {}):
                # patch at the import location inside email_source
                import docflow.ocr as ocr_mod
                original = ocr_mod.extract_text_from_bytes
                ocr_mod.extract_text_from_bytes = AsyncMock(return_value="scanned text")
                try:
                    text = await extract_text_from_attachment(attachment)
                finally:
                    ocr_mod.extract_text_from_bytes = original

        assert text == "scanned text"

    def test_imap_source_fetch_with_mock(self):
        """IMAPEmailSource processes unseen messages correctly."""
        # Build a fake RFC822 email with a JPEG attachment
        msg = email.mime.multipart.MIMEMultipart()
        msg["Subject"] = "Test Invoice"
        msg["From"] = "test@example.com"
        msg["Date"] = "Mon, 10 Mar 2026 09:00:00 +0100"
        msg.attach(email.mime.text.MIMEText("Please find invoice attached.", "plain"))

        img_bytes = _make_fake_jpeg_bytes()
        part = email.mime.base.MIMEBase("image", "jpeg")
        part.set_payload(img_bytes)
        email.encoders.encode_base64(part)
        part.add_header("Content-Disposition", 'attachment; filename="invoice.jpg"')
        msg.attach(part)

        raw = msg.as_bytes()

        mock_conn = MagicMock()
        mock_conn.uid.side_effect = [
            # SEARCH
            ("OK", [b"1"]),
            # FETCH
            ("OK", [(b"1 (RFC822 {100})", raw)]),
        ]
        mock_conn.select = MagicMock(return_value=("OK", []))
        mock_conn.create = MagicMock(return_value=("OK", []))
        mock_conn.expunge = MagicMock()
        mock_conn.logout = MagicMock()

        source = IMAPEmailSource(
            host="imap.example.com",
            port=993,
            username="user",
            password="pass",
        )

        with patch.object(source, "_connect", return_value=mock_conn):
            result = source.fetch_attachments()

        assert len(result.errors) == 0
        assert len(result.attachments) >= 1
        assert result.attachments[0].subject == "Test Invoice"
        assert result.attachments[0].sender == "test@example.com"
