# DocFlow

Automated document scanning, tagging, and archiving for macOS.

## Overview

DocFlow reads photos from an Apple Photos album, extracts text via the Apple Vision Framework (OCR), classifies documents using an LLM, saves them as PDFs, and stores metadata in a searchable SQLite database. A FastAPI web UI lets you view runs, search documents, and browse archives.

## Features

- **Apple Photos integration** — reads images from a named album (e.g. "Dokumente")
- **Native OCR** — uses Apple Vision Framework for high-quality text recognition
- **LLM classification** — supports Anthropic Claude, Ollama (local), and OpenRouter
- **PDF output** — saves documents in an organized folder structure
- **Full-text search** — SQLite FTS5 index over OCR text, type, tags, and filename
- **Web UI** — FastAPI dashboard at `http://localhost:8765`
- **Daily scheduler** — APScheduler cron job (configurable hour/minute)

## Requirements

- macOS 12+ (for Vision framework)
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager

## Setup

```bash
# Clone / copy project
cd docflow

# Install dependencies
uv sync
uv sync --extra macos   # macOS-specific: osxphotos + pyobjc

# Configure
cp .env.example .env
# Edit .env with your settings
```

## Usage

### Start web server + scheduler
```bash
uv run python -m docflow
```

### Run pipeline once manually
```bash
uv run python scripts/run_once.py
```

### Run tests
```bash
uv run pytest
```

## Configuration

All settings are in `.env` (or environment variables):

| Variable | Default | Description |
|---|---|---|
| `PHOTOS_ALBUM` | `Dokumente` | Apple Photos album name |
| `OUTPUT_DIR` | `~/Documents/DocFlow` | Where PDFs are saved |
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `ollama`, or `openrouter` |
| `ANTHROPIC_API_KEY` | — | Required for Anthropic |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model name |
| `OPENROUTER_API_KEY` | — | Required for OpenRouter |
| `OPENROUTER_MODEL` | `anthropic/claude-3-haiku` | OpenRouter model |
| `SCHEDULE_HOUR` | `2` | Cron hour for daily run |
| `SCHEDULE_MINUTE` | `0` | Cron minute for daily run |
| `DB_PATH` | `~/Documents/DocFlow/docflow.db` | SQLite database path |
| `WEB_HOST` | `127.0.0.1` | Web server host |
| `WEB_PORT` | `8765` | Web server port |

## Web UI

Visit `http://localhost:8765` after starting.

- **Dashboard** — last 10 runs with status and counts
- **Documents** — full-text search, filter by type/tag, link to saved PDF
- **Run detail** — full log for a specific run

## Architecture

```
Apple Photos → OCR (Vision) → LLM → PDF → SQLite
                                        ↓
                                   FastAPI Web UI
```

## LLM Prompt

DocFlow sends the OCR text to the LLM and expects a JSON response:

```json
{
  "doc_type": "Rechnung",
  "tags": ["Vodafone", "2026-03", "Telekommunikation"],
  "suggested_filename": "2026-03_Vodafone_Rechnung.pdf",
  "confidence": 0.95
}
```

Supported doc types (examples): Rechnung, Kontoauszug, Vertrag, Brief, Formular, Ausweis, Quittung, Sonstiges
