#!/usr/bin/env python3
"""Dokumentdatum fuer Bestandsdokumente nachziehen.

Fuer jedes Dokument ohne ``effective_date`` wird der gespeicherte OCR-Text noch
einmal durch das LLM geschickt, das genannte Datum wie in der Pipeline geprueft
(siehe ``doc_date.py``) und das Ergebnis in ``document_date`` / ``date_kind`` /
``effective_date`` / ``date_source`` geschrieben. Aussortierte Fotos und
Videos bekommen ohne LLM-Aufruf ihr Aufnahmedatum als wirksames Datum.

Dateinamen und Ablagepfade werden **nicht** angefasst — erst anschauen, dann
entscheiden, ob Dateien verschoben werden sollen.

Usage:
    uv run python scripts/backfill_dates.py --dry-run
    uv run python scripts/backfill_dates.py --limit 20
    uv run python scripts/backfill_dates.py
    uv run python scripts/backfill_dates.py --all      # auch bereits datierte neu pruefen
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

from docflow.config import get_settings
from docflow.db import Database
from docflow.doc_date import resolve_document_date
from docflow.llm import get_llm_provider

AUSSORTIERT = ("Foto", "Video")


def _photo_date(row: dict) -> datetime | None:
    raw = row.get("photo_date")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="nur anzeigen, nichts schreiben")
    parser.add_argument("--limit", type=int, default=0, help="hoechstens so viele LLM-Aufrufe")
    parser.add_argument("--all", action="store_true", help="auch Dokumente mit effective_date neu pruefen")
    parser.add_argument("--concurrency", type=int, default=4, help="parallele LLM-Aufrufe (Default 4)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)-8s %(name)s — %(message)s")
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(level))

    settings = get_settings()
    db = Database(settings.db_path)
    where = "" if args.all else "effective_date IS NULL"
    rows = db.iter_documents(where)

    # ── 1. Aussortierte Aufnahmen: Fotodatum ohne LLM ────────────────────────
    def braucht_llm(r: dict) -> bool:
        return r["doc_type"] not in AUSSORTIERT and bool((r.get("ocr_text") or "").strip())

    ohne_llm = [r for r in rows if not braucht_llm(r)]
    dokumente = [r for r in rows if braucht_llm(r)]
    if args.limit:
        dokumente = dokumente[: args.limit]

    print(f"DocFlow — Datums-Nachlauf ({'Probelauf' if args.dry_run else 'schreibend'})")
    print(f"  ohne LLM (Fotos/Videos/ohne Text): {len(ohne_llm)}")
    print(f"  Dokumente fuer das LLM:            {len(dokumente)}  (Provider: {settings.llm_provider})")
    print()

    foto_gesetzt = 0
    for r in ohne_llm:
        res = resolve_document_date(None, None, "", _photo_date(r))
        if res.source == "none":
            continue
        foto_gesetzt += 1
        if not args.dry_run:
            db.update_document_dates(r["id"], None, "none", res.effective_date_iso, res.source)
    print(f"  Fotodatum uebernommen: {foto_gesetzt} von {len(ohne_llm)}")

    if not dokumente:
        return 0

    # ── 2. Dokumente: LLM fragen, Antwort pruefen ────────────────────────────
    llm = get_llm_provider(settings)
    sem = asyncio.Semaphore(max(1, args.concurrency))
    ergebnis: Counter[str] = Counter()
    fehler: list[tuple[int, str]] = []
    beispiele: list[str] = []

    async def bearbeite(r: dict) -> None:
        async with sem:
            try:
                cls = await llm.classify_document(r["ocr_text"])
            except Exception as e:  # noqa: BLE001 — pro Dokument weiter, Lauf nicht abbrechen
                fehler.append((r["id"], str(e)))
                return
        res = resolve_document_date(cls.document_date, cls.date_kind, r["ocr_text"], _photo_date(r))
        ergebnis[res.source] += 1
        alt = (r.get("suggested_filename") or "")[:7]
        zeile = (f"  #{r['id']:<6} {r['doc_type']:<18} Datei {alt}  LLM {cls.document_date or '-':<10} "
                 f"{cls.date_kind:<9} -> {res.effective_date_iso or '-':<10} ({res.source}) {res.reason}")
        if args.verbose or len(beispiele) < 15:
            beispiele.append(zeile)
        if not args.dry_run:
            db.update_document_dates(
                r["id"], res.document_date_iso, cls.date_kind, res.effective_date_iso, res.source
            )

    await asyncio.gather(*(bearbeite(r) for r in dokumente))

    print()
    print("\n".join(beispiele))
    if len(beispiele) < len(dokumente) - len(fehler):
        print(f"  … ({len(dokumente) - len(fehler) - len(beispiele)} weitere, -v zeigt alle)")
    print()
    print(f"Ergebnis: {len(dokumente)} Dokumente")
    print(f"  Dokumentdatum bestaetigt: {ergebnis['document']}")
    print(f"  Fotodatum (Fallback):     {ergebnis['photo']}")
    print(f"  kein Datum:               {ergebnis['none']}")
    print(f"  LLM-Fehler:               {len(fehler)}")
    for doc_id, msg in fehler[:10]:
        print(f"    #{doc_id}: {msg}")
    if args.dry_run:
        print("\nProbelauf — nichts geschrieben.")
    return 0 if not fehler else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
