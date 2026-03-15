# CLAUDE.md — DocFlow Project Context

> This file is for AI coding agents (Claude Code, Codex, etc.). It describes the architecture,
> dev commands, extension points, testing strategy, and known limitations.

## Architecture Overview

```
Apple Photos (osxphotos)
    │
    ▼
OCR (Apple Vision / pyobjc)        Email (imaplib)
    │                                    │
    └────────────────┬───────────────────┘
                     ▼
              LLM Classification
         (Anthropic / Ollama / OpenRouter)
                     │
              DocumentClassification
              {doc_type, tags, filename, confidence}
                     │
           ┌─────────┴─────────┐
           ▼                   ▼
     PDF Creation         Storage Backend
    (img2pdf/Pillow)   (local / iCloud / S3)
           │                   │
           └─────────┬─────────┘
                     ▼
              SQLite + FTS5 (db.py)
                     │
              FastAPI Web UI
         (routes.py + Jinja2 templates)
```

## Module Descriptions

| Module | Purpose |
|---|---|
| `config.py` | All settings via pydantic-settings; reads `.env`; `get_settings()` is cached |
| `db.py` | SQLite + FTS5; `Database` class; schema + migrations; runs + documents tables |
| `ocr.py` | Apple Vision OCR; graceful fallback when pyobjc unavailable |
| `photos.py` | osxphotos adapter; `PhotoInfo` dataclass; `MockPhotosLibrary` for testing |
| `email_source.py` | IMAP reader; extracts PDF/image attachments; marks/moves processed messages |
| `pipeline.py` | Orchestrates: fetch → OCR → LLM → PDF → storage → DB |
| `scheduler.py` | APScheduler cron job wrapping pipeline; daily run at configured hour:minute |
| `llm/` | `base.py`: protocol + `DocumentClassification`; `anthropic.py`, `ollama.py`, `openrouter.py` |
| `storage/` | `base.py`: `StorageBackend` protocol; `local.py`, `icloud.py`, `generic_cloud.py` |
| `web/app.py` | FastAPI factory; attaches `db`, `settings`, `templates` to `app.state` |
| `web/routes.py` | Route handlers; HTML + JSON API endpoints |
| `web/templates/` | Jinja2; `base.html`, `index.html`, `documents.html`, `run_detail.html` |

## Data Flow

1. `Pipeline.run()` creates a DB run record (status=`running`)
2. Fetches photos from album via osxphotos (or MockPhotosLibrary in tests)
3. For each photo: OCR via Vision → LLM classify → write PDF → save via storage → insert DB record
4. If email enabled: IMAP fetch → extract attachments → same OCR/LLM/PDF/DB path
5. Run record updated with final status/counts/log

## Dev Commands

```bash
# Install dependencies (all platforms)
uv sync --dev

# Install macOS-specific extras (osxphotos + pyobjc)
uv sync --extra macos

# Run ALL tests
uv run pytest -v

# Run only unit tests (fast, no I/O)
uv run pytest -m unit -v

# Run only E2E tests (real SQLite + files, mocked APIs)
uv run pytest -m e2e -v

# Run with coverage
uv run pytest --cov=src/docflow --cov-report=term-missing

# Start web server + scheduler
uv run python -m docflow

# Run pipeline once manually
uv run python scripts/run_once.py
uv run python scripts/run_once.py --verbose

# Lint
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run mypy src/docflow --ignore-missing-imports
```

## How to Add a New LLM Provider

1. Create `src/docflow/llm/myprovider.py`
2. Implement `async def classify_document(self, ocr_text: str) -> DocumentClassification`
3. Use `build_prompt(ocr_text)` from `base.py` and `parse_classification_response(raw)` for parsing
4. Register in `llm/__init__.py` `get_llm_provider()` with a new elif branch
5. Add the provider name to the `Literal` in `config.py`
6. Add tests in `tests/test_llm.py`

## How to Add a New Storage Backend

1. Create `src/docflow/storage/myprovider.py`
2. Implement `name: str` property and `async def save(local_path, destination_path) -> str`
3. Register in `storage/__init__.py` `get_storage_backend()`
4. Add to the `Literal` in `config.py`
5. Add tests in `tests/e2e/test_e2e_storage.py`

## Testing Strategy

### Markers
- `@pytest.mark.unit` — pure logic, no file I/O, no network; fast (~ms)
- `@pytest.mark.e2e` — real SQLite + real file I/O; mocked: OCR/Vision, LLM, IMAP, S3

### Mock Boundaries
| Always mocked | Never mocked |
|---|---|
| Apple Vision OCR (`extract_text`) | SQLite database operations |
| osxphotos (use `MockPhotosLibrary`) | File system reads/writes |
| IMAP connections | PDF creation (Pillow/img2pdf) |
| LLM API calls (`classify_document`) | FastAPI routing |
| S3 (use moto) | Config/settings loading |

### Fixtures
- `tmp_dir` / `e2e_dir` — temporary directories (auto-cleaned)
- `db` / `e2e_db` — real SQLite in tmp dir
- `settings` / `e2e_settings` — Settings pointed at tmp dirs
- `mock_llm` — MagicMock with AsyncMock `classify_document`
- `fake_image` / `fake_jpeg` — real JPEG files created with Pillow

## Known Limitations

- **pyobjc / Vision**: macOS only. On Linux/Windows, OCR returns `""`. Tests mock this.
- **osxphotos**: macOS only. Always use `MockPhotosLibrary` in tests or CI.
- **iCloud Drive**: Only works on macOS with iCloud signed in. Path must exist.
- **S3 backend**: Requires `boto3` (optional dep). Tests use `moto` mock.
- **pdfplumber**: Required for PDF email attachments. Not in default deps — add if needed.
- **APScheduler background thread**: Uses `asyncio.new_event_loop()` per run.
- **FTS5**: SQLite must be compiled with FTS5 (standard on macOS/most Linux distros).

## DB Schema Reference

```sql
runs(id, started_at, finished_at, status, photos_found, docs_processed, errors, log)
documents(id, run_id, original_photo_id, original_filename, ocr_text,
          llm_provider, doc_type, tags, suggested_filename, saved_path, created_at,
          source, email_subject, email_sender, email_date,
          storage_backend, cloud_path)
documents_fts  -- FTS5 virtual table, synced via triggers
```

## Configuration Reference

See `.env.example` for all variables. Key ones:
- `LLM_PROVIDER`: `anthropic` | `ollama` | `openrouter`
- `STORAGE_BACKEND`: `local` | `icloud` | `s3`
- `EMAIL_ENABLED`: `true` to activate IMAP ingestion
- `SCHEDULE_HOUR` / `SCHEDULE_MINUTE`: daily cron time (UTC)

## CI / CD

- `.github/workflows/ci.yml` — unit tests on macOS-latest + lint on ubuntu-latest
- `.github/workflows/release.yml` — creates GitHub Release on `v*` tags
- `.github/workflows/security.yml` — weekly pip-audit + bandit

E2E tests are **skipped in CI** (`-m unit`) because:
1. They require macOS + pyobjc for full Vision/Photos path
2. CI uses ubuntu-latest for lint (no osxphotos)
3. Use `uv run pytest -m e2e` locally to run them

## Skills

See `skills/` for automation:
- `e2e-health/` — weekly E2E health check
- `security-audit/` — monthly pip-audit + bandit
- `docs-sync/` — verify docs match code
- `release/` — full release process

See `AGENTS.md` for agent maintenance guide.
