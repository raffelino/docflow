# Aus dem verlorenen `CLAUDE.md` (Juni-Stand)

Rekonstruiert am 2026-09-11 aus dem Sitzungskontext. Das `CLAUDE.md` im Repo ist der
März-Stand und passt zum Code — die folgenden Abschnitte kamen erst mit den
verlorenen Juni-Commits dazu und beschreiben teils Module, die es hier noch nicht
gibt (siehe `GAP.md`). Beim Wiederaufbau zurück ins `CLAUDE.md` übernehmen.

Der Abschnitt „Known Pitfalls" ist der wichtigste Teil: hart erarbeitetes Wissen,
das sich nicht aus dem Code ableiten lässt.

## Production Environment

- **URL**: `http://192.168.178.103:8765`
- **DB**: `/Users/rat/Documents/DocFlow/docflow.db`
- **Log**: `/tmp/docflow.log` (Server) + `~/.docflow/docflow.log` (structlog)
- **Server start**: `nohup .venv/bin/python -m docflow > /tmp/docflow.log 2>&1 &`
- **Scan scope**: ganze Photos-Library (`PHOTOS_SOURCE=all`); Album „Dokumente" wird
  per `FORCE_DOCUMENT_ALBUMS` immer als Dokument behandelt
- **LLM**: OpenRouter (`anthropic/claude-3-haiku`)

## Critical Config Rules

- `LLM_PROVIDER=openrouter` — **nicht auf anthropic ändern**, kein Key vorhanden
- `PHOTOS_ALBUM=Dokumente` — **nicht auf TestAlbum ändern**
- `PHOTOS_SOURCE` — sowohl `album` als auch `all` sind unterstützt. Produktion läuft
  mit `all`; der Pre-Classifier filtert Nicht-Dokumente, `FORCE_DOCUMENT_ALBUMS`
  umgeht ihn. Pro Lauf auch über `album_override="__all__"` wählbar.
- `_write_env_file` nutzt **Merge**-Logik, kein Überschreiben — sonst sind die
  API-Keys nach einem Settings-Speichern weg
- `photos_source`, `scan_only`, `llm_provider`, `web_host` sind **nicht** in
  `_SETTINGS_FIELDS` (absichtlich nicht über die UI konfigurierbar)
- `OPENROUTER_API_KEY` muss immer in `.env` stehen

## Known Pitfalls (learned the hard way)

- **E2E-Tests überschreiben `.env`**: `_write_env_file` wird mit Test-Settings
  aufgerufen → nach Testläufen steht `TestAlbum` und ein tmp-`OUTPUT_DIR` in `.env`.
  Nach jedem Testlauf prüfen:
  `grep -q "TestAlbum" .env && echo "WARNUNG: .env kontaminiert!"`
  Danach `PHOTOS_ALBUM=Dokumente` und `OUTPUT_DIR=~/Documents/DocFlow` wiederherstellen.
- **pillow-heif ist Pflicht**: HEIC-Dateien scheitern sonst mit `cannot identify
  image file`. `pip install pillow-heif`, und beim Pipelinestart
  `from pillow_heif import register_heif_opener; register_heif_opener()`.
- **FTS-Virtual-Table**: `DELETE FROM documents` scheitert an den Triggern.
  `WHERE 1=1` hilft nicht zuverlässig; Workaround ist Drop und Neuanlage oder
  `pragma writable_schema`.
- **iCloud-Fotos**: `ismissing=True`, wenn Photos.app keine lokale Kopie hat. Abhilfe:
  in macOS unter Systemeinstellungen → Datenschutz → Fotos den Zugriff erteilen.
- **Scan-State-Key**: der effektive Albumname, bei Full-Library-Scans `__all__`.
  Ändert sich der Albumname zwischen zwei Läufen, findet der inkrementelle Scan den
  alten State nicht und verhält sich wie ein Erstlauf. Ein Wechsel von
  `PHOTOS_SOURCE` zwischen `album` und `all` wechselt ebenfalls den Key — jeder Modus
  behält also seinen eigenen Cutoff.
- **`brctl download`** funktioniert für die Photos-Library **nicht** (liegt außerhalb
  des iCloud-Drive-Scopes).
- **AppleScript-Export** hängt bei iCloud-Fotos (60s+ Timeout). Stattdessen
  `osxphotos photo.export()` verwenden.
- **Videos** vor jedem Exportversuch aussortieren, sonst löst Photos.app eine
  Medienkonvertierung aus, die bei iCloud-only-Videos hängen bleibt.

## Album Override (Pre-Classifier-Bypass)

`FORCE_DOCUMENT_ALBUMS=Dokumente` — Alben in dieser Liste überspringen den
Pre-Classifier komplett, alles darin gilt als Dokument. In `config.py` als
`force_document_albums: str = "Dokumente"`, angewendet in `pipeline.py`.

## `.env` (Produktionswerte)

```
PHOTOS_SOURCE=all
PHOTOS_ALBUM=Dokumente
LLM_PROVIDER=openrouter
OPENROUTER_MODEL=anthropic/claude-3-haiku
OPENROUTER_API_KEY=<nur in .env, gitignored, niemals committen>
STORAGE_BACKEND=local
OUTPUT_DIR=~/Documents/DocFlow
ICLOUD_DOWNLOAD_TIMEOUT=300
ICLOUD_BATCH_SIZE=1
FORCE_DOCUMENT_ALBUMS=Dokumente
WEB_HOST=0.0.0.0
WEB_PORT=8765
SCHEDULE_HOUR=2
SCHEDULE_MINUTE=30
EMAIL_ENABLED=false
```

## Typischer Pipeline-Durchlauf

```
Pipeline.run() → DB Run-Record (status=running) →
Fotos laden (osxphotos: ganze Library oder Album) →
pro Foto:
  → OCR (Apple Vision) → Text
  → Pre-Classifier → document | photo | video
  → LLM klassifizieren (entfällt bei scan_only)
  → PDF erzeugen (img2pdf)
  → speichern (local/iCloud/S3)
  → DB-Eintrag mit Metadaten, Tokens, Kosten
→ Run-Record aktualisieren (success/error), Scan-State fortschreiben
```

## Zielpfad der PDFs

`OUTPUT_DIR/<Jahr>/<Monat>/<safe_filename>.pdf`, Jahr und Monat aus dem
Erstellungszeitpunkt des Dokuments.
