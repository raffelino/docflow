"""Abstract LLM interface and shared data types."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

CLASSIFICATION_PROMPT = """\
You are a document classification assistant. Analyze the following OCR text extracted from a scanned document and return a JSON object with exactly these fields:

- doc_type: The document type in German (e.g. "Rechnung", "Kontoauszug", "Vertrag", "Brief", "Formular", "Ausweis", "Quittung", "Lieferschein", "Mahnung", "Sonstiges")
- tags: A JSON array of relevant tags (strings) — include company names, dates (YYYY-MM), topics, amounts if visible
- suggested_filename: A safe filename with .pdf extension, format: Company_Type.pdf — WITHOUT a date prefix, the date is added by the system
- confidence: A float between 0.0 and 1.0 indicating how confident you are
- document_date: The date OF THE DOCUMENT ITSELF (invoice date, letter date, receipt timestamp, statement date), exactly as printed, formatted YYYY-MM-DD, or YYYY-MM if only month and year are printed. null if no such date is visible. Never guess and never use today's date.
- date_kind: "explicit" if document_date is clearly the document's own date; "inferred" if it is some other date in the text (birth date, valid-until, event date, due date) or you are unsure; "none" if document_date is null

Respond ONLY with the JSON object, no markdown, no explanation.

OCR TEXT:
---
{ocr_text}
---
"""


@dataclass
class DocumentClassification:
    doc_type: str
    tags: list[str] = field(default_factory=list)
    suggested_filename: str = "document.pdf"
    confidence: float = 0.5
    # Vom LLM genanntes Dokumentdatum (YYYY-MM-DD oder YYYY-MM) und dessen Art:
    # 'explicit' | 'inferred' | 'none'. Geprueft wird es in doc_date.py.
    document_date: str | None = None
    date_kind: str = "none"


@runtime_checkable
class LLMProvider(Protocol):
    async def classify_document(self, ocr_text: str) -> DocumentClassification:
        """Classify a document from its OCR text."""
        ...


def parse_classification_response(raw: str) -> DocumentClassification:
    """Parse JSON from LLM response, tolerating markdown fences."""
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = cleaned.rstrip("`").strip()

    data = json.loads(cleaned)

    return DocumentClassification(
        doc_type=str(data.get("doc_type", "Sonstiges")),
        tags=list(data.get("tags", [])),
        suggested_filename=str(data.get("suggested_filename", "document.pdf")),
        confidence=float(data.get("confidence", 0.5)),
        document_date=_optional_str(data.get("document_date")),
        date_kind=str(data.get("date_kind") or "none").strip().lower(),
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def build_prompt(ocr_text: str) -> str:
    return CLASSIFICATION_PROMPT.format(ocr_text=ocr_text)
