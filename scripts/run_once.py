#!/usr/bin/env python3
"""Manual trigger: run the DocFlow pipeline once and exit.

Usage:
    uv run python scripts/run_once.py
    uv run python scripts/run_once.py --verbose
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure src/ is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

from docflow.config import get_settings
from docflow.db import Database
from docflow.pipeline import Pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DocFlow pipeline once")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose log output")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level),
    )

    settings = get_settings()
    settings.ensure_dirs()

    db = Database(settings.db_path)
    pipeline = Pipeline(settings=settings, db=db)

    print(f"DocFlow — running pipeline once")
    print(f"  Album:    {settings.photos_album}")
    print(f"  LLM:      {settings.llm_provider}")
    print(f"  Storage:  {settings.storage_backend}")
    print(f"  Email:    {'enabled' if settings.email_enabled else 'disabled'}")
    print()

    run_id = asyncio.run(pipeline.run())
    run = db.get_run(run_id)

    print()
    print(f"Done — Run #{run_id}")
    print(f"  Status:     {run['status']}")
    print(f"  Processed:  {run['docs_processed']}")
    print(f"  Errors:     {run['errors']}")

    if args.verbose and run.get("log"):
        print("\n── Log ──────────────────────────────")
        print(run["log"])

    sys.exit(0 if run["status"] == "success" else 1)


if __name__ == "__main__":
    main()
