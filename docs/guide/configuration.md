# Konfiguration

Alle Einstellungen werden ueber Umgebungsvariablen oder die `.env`-Datei konfiguriert. Sie koennen auch ueber die Web-UI unter **Einstellungen** geaendert werden.

## Photos

| Variable | Standard | Beschreibung |
|---|---|---|
| `PHOTOS_SOURCE` | `album` | `album` fuer ein bestimmtes Album, `all` fuer die gesamte Mediathek |
| `PHOTOS_ALBUM` | `Dokumente` | Name des Albums in Apple Photos |

## LLM / KI-Modell

| Variable | Standard | Beschreibung |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `ollama` oder `openrouter` |
| `ANTHROPIC_API_KEY` | – | API-Key fuer Anthropic Claude |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama Server URL |
| `OLLAMA_MODEL` | `llama3.2` | Ollama Modellname |
| `OPENROUTER_API_KEY` | – | API-Key fuer OpenRouter |
| `OPENROUTER_MODEL` | `anthropic/claude-3-haiku` | OpenRouter Modellname |

## Speicher

| Variable | Standard | Beschreibung |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local`, `icloud` oder `s3` |
| `OUTPUT_DIR` | `~/Documents/DocFlow/output` | Ausgabeverzeichnis (lokal) |
| `ICLOUD_DOCFLOW_PATH` | `~/Library/Mobile Documents/.../DocFlow` | iCloud Drive Pfad |
| `S3_BUCKET` | – | S3 Bucket-Name |
| `S3_PREFIX` | `docflow/` | Praefix im Bucket |
| `S3_ENDPOINT_URL` | – | Fuer S3-kompatible Dienste (B2, MinIO, R2) |

## Zeitplan

| Variable | Standard | Beschreibung |
|---|---|---|
| `SCHEDULE_HOUR` | `2` | Stunde des taeglichen Laufs (UTC) |
| `SCHEDULE_MINUTE` | `0` | Minute des taeglichen Laufs |

## E-Mail

| Variable | Standard | Beschreibung |
|---|---|---|
| `EMAIL_ENABLED` | `false` | E-Mail-Eingang aktivieren |
| `EMAIL_IMAP_HOST` | `imap.gmail.com` | IMAP-Server |
| `EMAIL_IMAP_PORT` | `993` | IMAP-Port (SSL) |
| `EMAIL_ADDRESS` | – | E-Mail-Adresse |
| `EMAIL_PASSWORD` | – | App-Passwort |
| `EMAIL_FOLDER` | `INBOX` | Zu ueberwachender Ordner |
| `EMAIL_PROCESSED_FOLDER` | `DocFlow/Processed` | Ordner fuer verarbeitete Nachrichten |
| `EMAIL_FILTER_SUBJECT` | – | Optional: nur Nachrichten mit diesem Betreff |

## Webserver

| Variable | Standard | Beschreibung |
|---|---|---|
| `WEB_HOST` | `127.0.0.1` | `0.0.0.0` fuer externen Zugriff |
| `WEB_PORT` | `8765` | Server-Port |
