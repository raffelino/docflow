# E-Mail-Eingang

DocFlow kann automatisch E-Mail-Anhaenge verarbeiten. Aktiviere den E-Mail-Eingang in den Einstellungen oder per `.env`:

```bash
EMAIL_ENABLED=true
EMAIL_IMAP_HOST=imap.gmail.com
EMAIL_IMAP_PORT=993
EMAIL_ADDRESS=deine@email.de
EMAIL_PASSWORD=app-passwort-hier
```

::: warning Gmail App-Passwort
Fuer Gmail musst du ein [App-Passwort](https://support.google.com/accounts/answer/185833) erstellen, da das normale Passwort nicht fuer IMAP funktioniert.
:::

## Funktionsweise

1. DocFlow verbindet sich per IMAP mit dem Postfach
2. Sucht nach **ungelesenen** Nachrichten im konfigurierten Ordner
3. Extrahiert PDF- und Bild-Anhaenge
4. Verarbeitet sie wie Fotos (OCR → LLM → PDF → Archiv)
5. Verschiebt die Nachricht in den "Processed"-Ordner

## Konfiguration

| Variable | Beschreibung |
|---|---|
| `EMAIL_FOLDER` | Zu ueberwachender IMAP-Ordner (Standard: `INBOX`) |
| `EMAIL_PROCESSED_FOLDER` | Zielordner fuer verarbeitete Nachrichten |
| `EMAIL_FILTER_SUBJECT` | Optional: nur Nachrichten mit diesem Betreff verarbeiten |

## Unterstuetzte Anhaenge

- **Bilder** (JPEG, PNG) — werden per OCR verarbeitet
- **PDFs** — Text wird per pdfplumber extrahiert

::: tip Betreff-Filter
Mit `EMAIL_FILTER_SUBJECT` kannst du z.B. nur Nachrichten mit "Rechnung" im Betreff verarbeiten lassen.
:::
