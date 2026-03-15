# Changelog

All notable changes to DocFlow are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [0.1.0] — 2026-03-15

### Added

#### Core Pipeline
- **Apple Photos integration** via `osxphotos` — reads images from a named album (default: `Dokumente`)
- **OCR** via Apple Vision Framework (`pyobjc-framework-Vision`) — accurate multi-language text recognition
- **Graceful degradation** — OCR and Photos modules return safe defaults when pyobjc/osxphotos are unavailable (enables testing on non-macOS)
- **LLM document classification** — classifies document type, generates tags and suggested filename
- **PDF creation** — converts scanned images to single-page PDFs via `img2pdf` / Pillow fallback
- **APScheduler daily cron** — configurable run time (default: 02:00 UTC)

#### LLM Providers
- **Anthropic Claude** (`claude-3-5-haiku-20241022` default) via `anthropic` SDK
- **Ollama** (local models, e.g. `llama3.2`) via HTTP API
- **OpenRouter** (multi-model gateway) via HTTP API with OpenAI-compatible format

#### Storage Backends
- **Local filesystem** — saves PDFs to `OUTPUT_DIR/YYYY/MM/filename.pdf`
- **iCloud Drive** — copies files to `~/Library/Mobile Documents/com~apple~CloudDocs/DocFlow/`; iCloud syncs automatically
- **S3-compatible** — uploads to AWS S3, Backblaze B2, MinIO, Cloudflare R2 via `boto3`

#### Email Inbox Integration
- **IMAP** reader (`imaplib`) — fetches unseen messages from configured folder
- **Attachment extraction** — handles JPEG, PNG, TIFF, PDF attachments
- **PDF text extraction** — direct text extraction from PDF attachments via `pdfplumber`
- **Processed folder** — moves processed emails to `EMAIL_PROCESSED_FOLDER` (created if needed)
- **Subject filter** — optional substring filter on email subject
- **Email metadata in DB** — stores `source`, `email_subject`, `email_sender`, `email_date`

#### Database
- **SQLite** with WAL mode and foreign keys
- **FTS5 full-text search** — indexes OCR text, doc type, tags, and filename
- **Auto-triggers** — FTS index kept in sync with documents table via INSERT/UPDATE/DELETE triggers
- **Schema migrations** — idempotent `ALTER TABLE ADD COLUMN` migrations for upgrading existing DBs

#### Web UI
- **Dashboard** (`/`) — last 10 runs with status badges, counts, timestamps
- **Run detail** (`/runs/{id}`) — full log output + processed documents list
- **Documents** (`/documents`) — full-text search, filter by type/source/tag, paginated
- **Source icons** — 📷 Photos vs ✉️ Email with sender/subject/date shown for email docs
- **Storage badges** — shows backend (`local`, `icloud`, `s3`) and cloud path/URI
- **OCR preview** — collapsible OCR text preview per document
- **Manual trigger** — "▶ Jetzt ausführen" button triggers a pipeline run via background task
- **JSON API** — `/api/runs`, `/api/runs/{id}`, `/api/documents`, `/api/documents/{id}`

#### Configuration
- All settings via `pydantic-settings` — reads `.env`, environment variables, or code defaults
- Full `.env.example` with all options documented

#### Testing
- **Unit tests** (`@pytest.mark.unit`) — DB, OCR, LLM providers, pipeline helpers, web routes
- **E2E tests** (`@pytest.mark.e2e`) — real SQLite + real files, mocked external APIs:
  - `test_e2e_photos.py` — full photo pipeline
  - `test_e2e_email.py` — IMAP + attachment processing
  - `test_e2e_search.py` — FTS5 search accuracy
  - `test_e2e_scheduler.py` — scheduler integration
  - `test_e2e_web.py` — all web routes end-to-end
  - `test_e2e_storage.py` — local, iCloud, S3 (moto) storage

#### CI / CD
- **`ci.yml`** — unit tests on `macos-latest` + lint/mypy on `ubuntu-latest`
- **`release.yml`** — creates GitHub Release with CHANGELOG notes on `v*` tag push
- **`security.yml`** — weekly `pip-audit` + `bandit` + secret scan (Monday 08:00 UTC)

#### Agent Skills
- **`skills/e2e-health/`** — weekly E2E health check skill
- **`skills/security-audit/`** — monthly security audit skill
- **`skills/docs-sync/`** — documentation sync verification skill
- **`skills/release/`** — full release process skill

#### Documentation
- `README.md` — setup, usage, configuration table, architecture diagram
- `CLAUDE.md` — full AI agent context: architecture, dev commands, extension guide, test strategy
- `AGENTS.md` — agent maintenance guide, skill schedule, key files reference
- `CHANGELOG.md` — this file

[0.1.0]: https://github.com/docflow/docflow/releases/tag/v0.1.0
