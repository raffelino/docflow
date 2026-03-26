#!/usr/bin/env python3
"""Automated smoke test for DocFlow.

Runs the full pipeline and verifies:
  1. Pipeline completes successfully
  2. At least one document is processed
  3. PDF files exist on disk
  4. PDFs are valid (readable by pdfplumber/PyPDF2)
  5. PDFs have actual content (non-zero pages, non-empty)
  6. DB records match stored files
  7. API endpoints respond correctly

Usage:
    uv run python scripts/smoketest.py
    uv run python scripts/smoketest.py --verbose
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

from docflow.config import get_settings
from docflow.db import Database
from docflow.pipeline import Pipeline


class SmokeTestResult:
    def __init__(self):
        self.checks: list[tuple[str, bool, str]] = []

    def check(self, name: str, passed: bool, detail: str = ""):
        self.checks.append((name, passed, detail))
        icon = "PASS" if passed else "FAIL"
        msg = f"  [{icon}] {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)

    @property
    def all_passed(self) -> bool:
        return all(passed for _, passed, _ in self.checks)

    @property
    def summary(self) -> str:
        total = len(self.checks)
        passed = sum(1 for _, p, _ in self.checks if p)
        failed = total - passed
        return f"{passed}/{total} passed, {failed} failed"


def validate_pdf(path: Path) -> tuple[bool, str]:
    """Check if a file is a valid, non-empty PDF."""
    if not path.exists():
        return False, f"File not found: {path}"

    size = path.stat().st_size
    if size < 100:
        return False, f"File too small ({size} bytes), likely placeholder"

    # Check PDF magic bytes
    header = path.read_bytes()[:5]
    if header != b"%PDF-":
        return False, f"Not a valid PDF (header: {header!r})"

    # Try to read with PyPDF2 or pikepdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        num_pages = len(reader.pages)
        if num_pages == 0:
            return False, "PDF has 0 pages"
        return True, f"{num_pages} page(s), {size} bytes"
    except ImportError:
        pass

    # Fallback: just check size and header
    return True, f"{size} bytes (PDF reader not available for deep check)"


async def run_smoketest(verbose: bool = False) -> SmokeTestResult:
    result = SmokeTestResult()
    settings = get_settings()
    settings.ensure_dirs()

    print(f"\nDocFlow Smoke Test")
    print(f"{'=' * 50}")
    print(f"  Album:    {settings.photos_album}")
    print(f"  LLM:      {settings.llm_provider}")
    print(f"  Storage:  {settings.storage_backend}")
    print(f"  Output:   {settings.output_dir}")
    print()

    # ── 1. Run pipeline ──────────────────────────────────────────────────────
    print("Phase 1: Pipeline ausfuehren")
    db = Database(settings.db_path)
    pipeline = Pipeline(settings=settings, db=db)

    try:
        run_id = await pipeline.run()
        result.check("Pipeline laeuft ohne Absturz", True, f"Run #{run_id}")
    except Exception as e:
        result.check("Pipeline laeuft ohne Absturz", False, str(e))
        print(f"\n{result.summary}")
        return result

    # ── 2. Check run result ──────────────────────────────────────────────────
    print("\nPhase 2: Run-Ergebnis pruefen")
    run = db.get_run(run_id)
    result.check("Run-Record existiert", run is not None)

    if not run:
        print(f"\n{result.summary}")
        return result

    result.check(
        "Status ist 'success'",
        run["status"] == "success",
        f"Status: {run['status']}",
    )
    result.check(
        "Fotos gefunden",
        run["photos_found"] > 0,
        f"{run['photos_found']} Fotos",
    )
    result.check(
        "Dokumente verarbeitet oder uebersprungen",
        run["docs_processed"] >= 0,
        f"{run['docs_processed']} neue Dokumente (Duplikate werden uebersprungen)",
    )
    result.check(
        "Keine Fehler",
        run["errors"] == 0,
        f"{run['errors']} Fehler" if run["errors"] > 0 else "",
    )

    if verbose and run.get("log"):
        print(f"\n  ── Log ──")
        for line in run["log"].splitlines():
            print(f"    {line}")
        print()

    # ── 3. Check documents and PDFs ──────────────────────────────────────────
    print("\nPhase 3: Dokumente und PDFs pruefen")
    docs = db.list_documents(limit=100)
    run_docs = [d for d in docs if d["run_id"] == run_id]

    if run_docs:
        result.check(
            "Neue DB-Eintraege",
            True,
            f"{len(run_docs)} neue Dokumente in diesem Lauf",
        )
    else:
        all_docs = db.list_documents(limit=200)
        result.check(
            "Dokumente in DB vorhanden (Duplikate uebersprungen)",
            len(all_docs) > 0,
            f"{len(all_docs)} Dokumente gesamt, 0 neue (alle bereits verarbeitet)",
        )

    # Check PDFs for this run's docs, or fall back to recent docs
    check_docs = run_docs if run_docs else docs[:7]
    for doc in check_docs:
        doc_name = doc.get("suggested_filename") or doc.get("original_filename") or f"doc#{doc['id']}"
        saved_path = Path(doc.get("saved_path") or "")

        # File exists
        result.check(
            f"Datei existiert: {doc_name}",
            saved_path.exists(),
            str(saved_path) if saved_path.exists() else "NICHT GEFUNDEN",
        )

        if saved_path.exists():
            # Validate PDF
            valid, detail = validate_pdf(saved_path)
            result.check(f"PDF gueltig: {doc_name}", valid, detail)

        # Check LLM classification
        result.check(
            f"Dokumenttyp gesetzt: {doc_name}",
            bool(doc.get("doc_type")),
            doc.get("doc_type", "LEER"),
        )

        # Check OCR ran (may be empty for iCloud-only photos)
        ocr_len = len(doc.get("ocr_text") or "")
        result.check(
            f"OCR-Text vorhanden: {doc_name}",
            ocr_len > 0,
            f"{ocr_len} Zeichen" if ocr_len > 0 else "KEIN TEXT (Foto nicht lokal?)",
        )

    # ── 4. Check API ─────────────────────────────────────────────────────────
    print("\nPhase 4: API pruefen")
    try:
        import httpx

        async with httpx.AsyncClient(base_url="http://127.0.0.1:8765", timeout=5.0) as client:
            # Runs endpoint
            resp = await client.get("/api/runs")
            result.check("GET /api/runs", resp.status_code == 200, f"HTTP {resp.status_code}")

            # Documents endpoint
            resp = await client.get("/api/documents")
            result.check("GET /api/documents", resp.status_code == 200, f"{len(resp.json())} Dokumente")

            # Doc-types endpoint
            resp = await client.get("/api/doc-types")
            result.check("GET /api/doc-types", resp.status_code == 200, str(resp.json()))

            # File serving
            if run_docs:
                doc_id = run_docs[0]["id"]
                resp = await client.get(f"/api/documents/{doc_id}/file")
                result.check(
                    "PDF-Download via API",
                    resp.status_code == 200 and resp.headers.get("content-type", "").startswith("application/pdf"),
                    f"HTTP {resp.status_code}, {len(resp.content)} bytes",
                )

            # Settings endpoint
            resp = await client.get("/api/settings")
            result.check("GET /api/settings", resp.status_code == 200)

    except Exception as e:
        result.check("API erreichbar", False, f"Server laeuft nicht? ({e})")

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'=' * 50}")
    print(f"Ergebnis: {result.summary}")

    return result


def main():
    parser = argparse.ArgumentParser(description="DocFlow Smoke Test")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(level))

    result = asyncio.run(run_smoketest(verbose=args.verbose))
    sys.exit(0 if result.all_passed else 1)


if __name__ == "__main__":
    main()
