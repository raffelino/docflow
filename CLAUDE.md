# CLAUDE.md — DocFlow Project Context

> This file is for AI coding agents (Claude Code, Codex, etc.). It describes the architecture,
> dev commands, extension points, testing strategy, and known limitations.

## Production Environment

- **URL**: `http://192.168.178.103:8765`
- **DB**: `/Users/rat/Documents/DocFlow/docflow.db`
- **Log**: `/tmp/docflow.log` (Server) + `~/.docflow/docflow.log` (structlog)
- **Server start**: `cd ~/git/docflow && nohup .venv/bin/python -m docflow > /tmp/docflow.log 2>&1 &`
- **Repo**: `~/git/docflow` — **nicht** unter `~/.openclaw/workspace/`, dort wurde das
  Verzeichnis am 2026-09-08 von einem naechtlichen Job geloescht (siehe `recovery/`)
- **LLM**: OpenRouter (`anthropic/claude-3-haiku`)

## Critical Config Rules

- **Nach jedem Commit pushen.** Vier Commits gingen verloren, weil sie nur lokal lagen
  und das Verzeichnis samt `.git` verschwand. `git log origin/main..HEAD` pruefen —
  ein konfigurierter Upstream heisst nicht, dass er aktuell ist.
- `LLM_PROVIDER=openrouter` — nicht auf `anthropic` aendern, kein Key vorhanden
- `PHOTOS_ALBUM=Dokumente` — nicht auf `TestAlbum` aendern
- `PHOTOS_SOURCE` — `album` und `all` sind beide unterstuetzt. Bei `all` filtert der
  Pre-Classifier, `FORCE_DOCUMENT_ALBUMS` umgeht ihn. Pro Lauf auch ueber
  `album_override="__all__"`.
- `photos_source`, `llm_provider` und `web_host` stehen in `_READONLY_FIELDS`
  (`web/routes.py`): sichtbar, aber nicht ueber die UI aenderbar.
- `_write_env_file` **mergt** zeilenweise. Niemals auf Ueberschreiben umstellen —
  sonst loescht ein Klick auf "Speichern" den `OPENROUTER_API_KEY`.
- `OPENROUTER_API_KEY` muss immer in `.env` stehen (gitignored).

## Known Pitfalls (learned the hard way)

- **E2E-Tests und die `.env`** — *behoben am 2026-09-12, zweifach abgesichert:*
  Der Settings-Endpoint schreibt nach `app.state.env_path` (Tests lenken das in ihr
  tmp-Verzeichnis um), und die Test-Fixtures erzeugen `Settings(_env_file=None)`,
  lesen die Projekt-`.env` also nicht mehr. Zusammen mit der Merge-Logik ist der
  API-Key damit dreifach geschuetzt. Vorher hat ein Testlauf ihn geloescht.
  Beides hat Regressionstests — nicht zurueckbauen.
- **pillow-heif ist Pflicht** und steht in `pyproject.toml`. Fehlt es, scheitert jedes
  `Image.open` auf HEIC mit `UnidentifiedImageError` — das sieht im Log wie ein
  unlesbares Foto aus, nicht wie eine fehlende Abhaengigkeit, und sortiert
  HEIC-Dokumente als Fotos aus. Registriert wird ueber `imaging.ensure_heif_support()`.
- **AppleScript-Export** haengt bei iCloud-Fotos im Timeout. Stattdessen
  `osxphotos photo.export(use_photos_export=True, timeout=...)`. Lokale HEIC-Dateien
  werden gar nicht mehr exportiert, Pillow liest sie direkt.
- **Videos** vor jedem Exportversuch aussortieren (`pre_classifier.is_video`), sonst
  startet Photos.app eine Medienkonvertierung, die bei iCloud-only-Videos haengt.
- **Aussortierte Aufnahmen muessen in die DB** (als `Foto`/`Video`, ohne OCR-Text).
  Ohne den Eintrag greift der UUID-Dedup nicht und alle ~15.900 Fotos laufen jede
  Nacht neu durch die Texterkennung.
- **Scan-State-Key** ist der effektive Albumname, beim Vollscan `__all__`. Ein Wechsel
  von `PHOTOS_SOURCE` wechselt den Key — jeder Modus hat seinen eigenen Cutoff.
  Der Cutoff wird als **Startzeitpunkt** des Laufs gespeichert, nicht als Endzeit,
  sonst entsteht eine Luecke fuer alles, was waehrend des Laufs hinzukommt.
  Fortgeschrieben wird nur nach erfolgreichem Lauf ohne Datumsfilter.
- **`date_added` ist tz-aware**, der Scan-State naiv. Direkt vergleichen wirft
  `TypeError` — `photos._added_before_cutoff` normalisiert beide Seiten.
- **`brctl download`** funktioniert fuer die Photos-Library nicht.
- **FTS-Virtual-Table**: `DELETE FROM documents` scheitert an den Triggern.
- **iCloud-Fotos**: `ismissing=True`, wenn keine lokale Kopie da ist. Zugriff in
  Systemeinstellungen -> Datenschutz -> Fotos erteilen.

## Pre-Classifier (Kostenbremse)

`pre_classifier.py` entscheidet vor dem LLM, ob eine Aufnahme ein Dokument ist.
Schwelle: 250 Zeichen OCR-Text. An echten Daten kalibriert (200 Fotos der Library
gegen 871 klassifizierte Dokumente): 100 % Recall bei 2,5 % Falsch-Positiven.

**Nicht** auf Screenshots filtern. Das Muster trifft 54,6 % der `Sonstiges`-Eintraege,
aber auch 36,7 % der echten Dokumente — Online-Rechnungen und Tickets liegen als
Screenshot vor. Ein Regressionstest haelt das fest.

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
           ┌─────────┴─────────┐
           ▼                   ▼
    FastAPI JSON API      React SPA
    (routes.py)        (Vite + Tailwind)
```

## Frontend Architecture

### Stack
- **React 19** + TypeScript (Vite build)
- **Tailwind CSS v4** (utility-first styling)
- **shadcn/ui-inspired** components (custom, no dependency)
- **Lucide React** icons
- **React Router** v7 (client-side routing)

### Structure
```
frontend/
├── src/
│   ├── main.tsx              # Entry point with BrowserRouter
│   ├── App.tsx               # Route definitions
│   ├── lib/
│   │   ├── api.ts            # API client (typed fetch wrappers)
│   │   └── utils.ts          # cn(), formatDate(), truncate()
│   ├── components/
│   │   ├── Layout.tsx        # Header/Nav + Outlet
│   │   ├── StatusBadge.tsx   # Run status (success/error/running)
│   │   ├── SourceBadge.tsx   # Document source (photos/email)
│   │   └── StorageBadge.tsx  # Storage backend indicator
│   └── pages/
│       ├── Dashboard.tsx     # Stats cards + runs table
│       ├── Documents.tsx     # Search/filter + document table
│       ├── RunDetail.tsx     # Single run view with log
│       └── Settings.tsx      # Configuration form
├── index.html
├── vite.config.ts            # Proxy to FastAPI, path aliases
├── package.json
└── tsconfig.app.json
```

### SPA Integration
- React app is built to `frontend/dist/` via `npm run build`
- Build output is copied to `src/docflow/web/static/`
- FastAPI serves static files and falls back to `index.html` for SPA routes
- API routes (`/api/*`) are handled by FastAPI, everything else by React Router
- During development: `npm run dev` (port 5173) proxies API to FastAPI (port 8765)

### Design System
- **Primary:** `hsl(211 100% 45%)` (#0071e3, Apple blue)
- **Background:** `hsl(0 0% 98%)` (light gray)
- **Cards:** White with subtle border + shadow
- **Nav:** Dark `#1d1d1f`
- **Typography:** System fonts (-apple-system, SF Pro Display)
- **Badges:** Color-coded with icon (StatusBadge, SourceBadge, StorageBadge)
- **Layout:** Responsive, max-w-7xl centered

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
| `web/app.py` | FastAPI factory; serves React SPA + API; attaches `db`, `settings` to `app.state` |
| `web/routes.py` | JSON API endpoints + legacy Jinja2 HTML routes |
| `web/static/` | Built React frontend (generated by `scripts/build_frontend.sh`) |
| `web/templates/` | Jinja2 templates (legacy fallback, kept for compatibility) |
| `frontend/` | React SPA source code (Vite + TypeScript + Tailwind) |

## Typical Application Flow (User Journey)

### 1. Erster Start
```
User startet DocFlow → Server auf Port 8765 →
Browser oeffnet Dashboard → Keine Laeufe vorhanden →
User klickt "Jetzt ausfuehren" → Pipeline startet im Hintergrund
```

### 2. Pipeline-Durchlauf
```
Pipeline.run() → DB Run-Record (status=running) →
Photos aus Album laden (osxphotos) →
Fuer jedes Foto:
  → OCR (Apple Vision) → Text extrahieren
  → LLM (Anthropic/Ollama/OpenRouter) → Klassifizieren
  → PDF erstellen (img2pdf)
  → Speichern (local/iCloud/S3)
  → DB-Eintrag mit Metadaten
→ Run-Record aktualisieren (status=success/error)
```

### 3. Dokumente durchsuchen
```
User oeffnet /documents → Volltextsuche (FTS5) →
Filter nach Typ/Quelle → Klick auf Tag filtert weiter →
OCR-Vorschau aufklappen → Pfad zum gespeicherten PDF
```

### 4. Einstellungen aendern
```
User oeffnet /settings → Formular bearbeiten →
Speichern → .env wird aktualisiert →
Aenderungen sofort wirksam (in-memory update)
```

### 5. Automatischer Betrieb
```
APScheduler → Taeglicher Cron-Job (konfigurierte UTC-Zeit) →
Pipeline laeuft automatisch → Ergebnisse im Dashboard sichtbar
```

## API Reference

### JSON API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/runs?limit=10` | Liste der Pipeline-Laeufe |
| GET | `/api/runs/{id}` | Einzelner Lauf (404 wenn nicht gefunden) |
| GET | `/api/documents?q=&doc_type=&source=&run_id=&limit=&offset=` | Dokumente suchen/filtern |
| GET | `/api/documents/{id}` | Einzelnes Dokument |
| GET | `/api/doc-types` | Liste verfuegbarer Dokumenttypen |
| GET | `/api/settings` | Aktuelle Einstellungen (ohne Secrets) |
| POST | `/api/settings` | Einstellungen aktualisieren (JSON body) |
| POST | `/runs/trigger` | Pipeline manuell starten |

## Dev Commands

```bash
# ── Backend ──────────────────────────────────────────────
# Install dependencies (all platforms)
uv sync --dev

# Install macOS-specific extras (osxphotos + pyobjc)
uv sync --extra macos

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

# ── Frontend ─────────────────────────────────────────────
# Install frontend dependencies
cd frontend && npm install

# Start dev server (port 5173, proxies API to 8765)
cd frontend && npm run dev

# Build frontend for production
cd frontend && npm run build

# Build and deploy to Python package
./scripts/build_frontend.sh

# ── Tests ────────────────────────────────────────────────
# Run ALL tests
uv run pytest -v

# Run only unit tests (fast, no I/O)
uv run pytest -m unit -v

# Run only E2E tests (real SQLite + files, mocked APIs)
uv run pytest -m e2e -v

# Run with coverage
uv run pytest --cov=src/docflow --cov-report=term-missing
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

### E2E Test Coverage Gaps
- **Config module** (`config.py`): No unit tests for Settings class validation
- **Email source** (`email_source.py`): No unit tests, only E2E
- **Scheduler** (`scheduler.py`): No unit tests, only E2E
- **React UI**: No Playwright/Cypress tests yet (future)

## Known Limitations

- **pyobjc / Vision**: macOS only. On Linux/Windows, OCR returns `""`. Tests mock this.
- **osxphotos**: macOS only. Always use `MockPhotosLibrary` in tests or CI.
- **iCloud Drive**: Only works on macOS with iCloud signed in. Path must exist.
- **S3 backend**: Requires `boto3` (optional dep). Tests use `moto` mock.
- **pdfplumber**: Required for PDF email attachments. Not in default deps — add if needed.
- **APScheduler background thread**: Uses `asyncio.new_event_loop()` per run.
- **FTS5**: SQLite must be compiled with FTS5 (standard on macOS/most Linux distros).
- **Frontend build**: Requires Node.js 18+ for `npm run build`.

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
- `WEB_HOST`: `127.0.0.1` (local) or `0.0.0.0` (external access)
- `WEB_PORT`: default `8765`

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
