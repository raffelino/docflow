# Backend-Architektur

## Verzeichnisstruktur

```
src/docflow/
├── __main__.py          # Entry Point
├── config.py            # Pydantic Settings
├── db.py                # SQLite + FTS5
├── ocr.py               # Apple Vision OCR
├── photos.py            # osxphotos Adapter
├── email_source.py      # IMAP Reader
├── pipeline.py          # Orchestrierung
├── scheduler.py         # APScheduler Cron
├── llm/
│   ├── base.py          # Protocol + Datenklassen
│   ├── anthropic.py     # Anthropic Claude
│   ├── ollama.py        # Ollama (lokal)
│   └── openrouter.py    # OpenRouter
├── storage/
│   ├── base.py          # StorageBackend Protocol
│   ├── local.py         # Lokales Dateisystem
│   ├── icloud.py        # iCloud Drive
│   └── generic_cloud.py # S3-kompatibel
└── web/
    ├── app.py           # FastAPI Factory
    ├── routes.py        # API Endpoints
    ├── static/          # Gebautes React-Frontend
    └── templates/       # Jinja2 (Legacy)
```

## Modulbeschreibungen

### `config.py`
Zentrale Konfiguration via `pydantic-settings`. Liest `.env`-Datei, expandiert Pfade und validiert Werte. `get_settings()` ist per `@lru_cache` gecacht.

### `db.py`
SQLite-Datenbank mit FTS5 Volltextsuche. WAL-Modus fuer Concurrent Access. Triggers synchronisieren den FTS-Index automatisch bei Insert/Update/Delete.

### `pipeline.py`
Orchestriert den gesamten Verarbeitungsfluss. Erstellt Run-Records, verarbeitet Fotos und E-Mails, faengt Fehler pro Dokument ab und aktualisiert den Run-Status.

### `scheduler.py`
APScheduler BackgroundScheduler mit CronTrigger. Laeuft in eigenem Thread mit eigenem Event-Loop (wegen async Pipeline in sync APScheduler-Kontext).

### `ocr.py`
Wrapper um Apple Vision Framework via pyobjc. Laeuft in Thread-Executor um den Event-Loop nicht zu blockieren. Gibt leeren String zurueck wenn Vision nicht verfuegbar ist.

## Datenbank-Schema

```sql
-- Pipeline-Laeufe
runs(
  id, started_at, finished_at, status,
  photos_found, docs_processed, errors, log
)

-- Verarbeitete Dokumente
documents(
  id, run_id, original_photo_id, original_filename,
  ocr_text, llm_provider, doc_type, tags,
  suggested_filename, saved_path, created_at,
  source, email_subject, email_sender, email_date,
  storage_backend, cloud_path
)

-- Volltextsuche (automatisch synchronisiert)
documents_fts USING fts5(
  ocr_text, doc_type, tags, suggested_filename
)
```
