# Anwendungsflow

## Uebersicht

```
iPhone/iPad                    E-Mail-Postfach
    │                               │
    ▼                               ▼
Apple Photos Album          IMAP (Gmail, etc.)
    │                               │
    └───────────┬───────────────────┘
                ▼
         DocFlow Pipeline
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
   OCR    KI-Klassif.    PDF-Erstellung
    │           │           │
    └───────────┼───────────┘
                ▼
    ┌───────────┼───────────┐
    ▼           ▼           ▼
  Lokal     iCloud        S3
                │
                ▼
        SQLite + FTS5
                │
                ▼
          React Web-UI
```

## 1. Fotos aufnehmen

Fotografiere Dokumente mit dem iPhone/iPad. Die Fotos landen in Apple Photos und werden einem Album zugeordnet (z.B. "Dokumente").

::: tip Tipp
Aktiviere in den macOS Systemeinstellungen unter **Fotos > iCloud** die Option **"Originale auf diesen Mac laden"**, damit DocFlow auf die vollen Bilddateien zugreifen kann.
:::

## 2. Pipeline-Verarbeitung

Die Pipeline wird entweder **manuell** (Button "Jetzt ausfuehren" im Dashboard) oder **automatisch** (taeglicher Cron-Job) gestartet.

### Photos-Phase

Fuer jedes Foto im konfigurierten Album:

1. **OCR** — Apple Vision extrahiert den Text aus dem Bild
2. **LLM-Klassifikation** — Das LLM analysiert den OCR-Text und liefert:
   - `doc_type`: Dokumenttyp (Rechnung, Vertrag, Brief, ...)
   - `tags`: Relevante Schlagwoerter
   - `suggested_filename`: Vorgeschlagener Dateiname
   - `confidence`: Konfidenzwert (0.0 - 1.0)
3. **PDF-Erstellung** — Das Foto wird in ein PDF konvertiert (img2pdf)
4. **Speicherung** — Das PDF wird im gewaehlten Backend abgelegt: `YYYY/MM/dateiname.pdf`
5. **Indexierung** — Metadaten werden in SQLite mit FTS5-Index gespeichert

### Email-Phase (optional)

Wenn `EMAIL_ENABLED=true`:

1. IMAP-Verbindung herstellen
2. Ungelesene Nachrichten mit PDF/Bild-Anhaengen suchen
3. Selbe Verarbeitung wie Photos (OCR → LLM → PDF → Speichern)
4. Verarbeitete Nachrichten in den "Processed"-Ordner verschieben

## 3. Dokumente durchsuchen

Das Web-UI bietet:

- **Volltextsuche** ueber OCR-Text, Dateinamen und Tags
- **Filter** nach Dokumenttyp und Quelle (Photos/Email)
- **OCR-Vorschau** zum schnellen Pruefen des extrahierten Textes
- **Pagination** fuer grosse Dokumentmengen

## 4. Automatischer Betrieb

Der APScheduler fuehrt die Pipeline taeglich zur konfigurierten Uhrzeit (UTC) aus. Neue Fotos im Album werden automatisch verarbeitet — der Benutzer muss nichts weiter tun.

::: info Misfire-Toleranz
Falls der Server zum geplanten Zeitpunkt nicht laeuft, wird der Job innerhalb einer Stunde nachgeholt (Misfire Grace Time: 1h).
:::
