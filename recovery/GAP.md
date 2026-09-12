# Lücke zwischen diesem Repo-Stand und dem verlorenen Produktionsstand

Erhoben am 2026-09-11 durch Vergleich des Klons (`c3857c7`, 2026-03-26) mit dem
Schema der überlebenden Produktions-DB und dem rekonstruierten `CLAUDE.md`.

Verloren sind vier nie gepushte Commits (siehe `memory`-Eintrag `repo-loss-2026-09-08`).
Die beiden Juni-Commits enthielten deutlich mehr als ihre Titel vermuten lassen —
die folgende Liste ist die belastbare Untergrenze.

## Komplett fehlende Module

| Modul | Belegt durch | Zweck |
|---|---|---|
| `src/docflow/pre_classifier.py` | Run-Logs (`Pre-classified as: document/photo`), `_VIDEO_EXTENSIONS`-Import in `pipeline.py` | Trennt Fotos von Dokumenten, damit `PHOTOS_SOURCE=all` über 15.887 Fotos bezahlbar bleibt; liefert auch die Video-Erkennung |
| `src/docflow/keychain.py` | Commit-Titel `ccde5d1`, `resolve_email_password(settings)` | Email-Passwort aus dem macOS-Schlüsselbund statt aus `.env` |

## `photos.py` — Lazy-Iteratoren fehlen vollständig

Aktuell: `get_photos_in_album(album_name) -> list[PhotoInfo]` und `get_all_photos()`,
beide eager, ohne Parameter. `PhotoInfo` hat nur `uuid`, `filename`, `path`,
`original_filename`.

Fehlt:
- `iter_photos_in_album(album_name, icloud_timeout, date_from, date_to, skip_cloud_only, scan_cutoff)` als Generator
- `iter_all_photos(...)` mit derselben Signatur ohne `album_name`
- `count_photos_in_album(...)` / `count_all_photos(...)` — zählen ohne Export, damit die Fortschrittsanzeige sofort steht
- `_matches_date_range(p, date_from, date_to)`
- `_find_album(album_name)`
- iCloud-Download-Pfad mit Timeout pro Foto, `ismissing`-Behandlung, `skip_cloud_only`
- Video-Erkennung vor dem Export (verhindert Hänger bei iCloud-Videos)
- `PhotoInfo`-Felder `date`, `photo_date`, `date_added`
- `_cleanup_temp_export`
- `_added_before_cutoff` (siehe `2026-09-04-incremental-scan-cutoff.md`)
- die entsprechenden `MockPhotosLibrary`-Pendants

## `pipeline.py` — Orchestrierung ist eine andere

Aktuell: eager `for photo in photos`, `_log` heißt `log`, `_process_emails(run_id, log)`.

Fehlt:
- Inkrementeller Scan: `get_scan_state(album_key)` / Cutoff / `update_scan_state`, Key ist der effektive Albumname bzw. `__all__`
- `album_override` inkl. `__all__`, `date_from`/`date_to` als Lauf-Parameter
- `scan_all`-Zweig mit `effective_album`
- `force_document_albums` (Pre-Classifier-Bypass für „Dokumente")
- `cost_budget`, `min_disk_gb`, `reset_cancel()`/Abbruch, `update_run_progress`
- Token- und Kostenerfassung pro LLM-Aufruf
- Dedup über `file_hash` mit `document_exists`
- `scan_only`-Modus (kein LLM)
- `_log`-Callback plus `log_lines` für das Run-Log
- HEIC-Unterstützung: `register_heif_opener()` beim Pipelinestart

## `db.py` — Schema ist älter als die Produktions-DB

Die DB hat 25 Spalten in `documents`, der Code kennt 18. Fehlende Spalten und
Strukturen, die der Code anlegen bzw. schreiben muss:

- `documents`: `manually_classified`, `llm_classified`, `photo_date`,
  `prompt_tokens`, `completion_tokens`, `llm_cost_usd`, `file_size_bytes`
- `runs`: `photos_skipped`
- Tabelle `scan_state(album_key, last_scanned_at, photo_count)` — existiert in der DB,
  Zugriffsmethoden fehlen im Code
- `document_exists(file_hash=...)`, `update_run_progress(...)`

Wichtig: SQLite verträgt die zusätzlichen Spalten, der März-Code schreibt sie nur
nicht. Ein Start gegen die Produktions-DB beschädigt nichts, liefert aber
unvollständige Datensätze.

## `config.py`

Fehlen mindestens: `force_document_albums` (Default `"Dokumente"`), `scan_only`,
`icloud_download_timeout`, `icloud_batch_size`.

## Web / Frontend

Aus Commit-Titel `b57eeaf` („wire up settings/sorting/thumbnails") und `CLAUDE.md`:
Settings-Felder in `_SETTINGS_FIELDS`, Sortierung in der Dokumentenliste,
Thumbnails, `_write_env_file` mit **Merge**-Logik (nicht überschreiben, sonst sind
die API-Keys beim Settings-Speichern weg).

## Was NICHT fehlt

`6aef0bc` (Full-Library-Scan-Grundlage), `b4174b5` (Settings-Seite),
`c3857c7` (React-SPA, VitePress-Docs, iCloud-Export, Dedup-Grundlage) sind im Klon
enthalten. Die HEIC-Fehlklassifikation aus `b57eeaf` ist damit wieder offen.

## Reihenfolge für den Wiederaufbau — **abgeschlossen 2026-09-12**

1. ~~`pre_classifier.py`~~ `fd85c22` — an echten Daten kalibriert, 100 % Recall auf
   871 Dokumenten bei 2,5 % Falsch-Positiven. Dazu `pillow-heif` als Dependency
   (`8ce5a49`), die Ursache der HEIC-Fehlklassifikation.
2. ~~Lazy-Iteratoren in `photos.py`~~ `61c8db2` — inkl. `date_added`, `count_*` ohne
   Dateizugriff, iCloud-Download über osxphotos statt AppleScript, `uuids_in_albums`
   für `FORCE_DOCUMENT_ALBUMS` beim Vollscan.
3. ~~Inkrementeller Scan~~ `61c8db2` + `a39d592` — `scan_state` mit den Spaltennamen
   der Produktions-DB, Cutoff als Startzeitpunkt des Laufs, `total_scanned` als
   Bereichsgröße.
4. ~~Cutoff in den Iteratoren~~ — direkt richtig gebaut, die Notiz aus
   `2026-09-04-incremental-scan-cutoff.md` ist damit eingelöst.
5. ~~`keychain.py`~~ `1ab0d24` — Email-Passwort aus dem Schlüsselbund, Rückfall auf
   `EMAIL_PASSWORD`.
6. ~~Web-Teile~~ `15f9b4e` + `fbfc3b8` — `_write_env_file` mergt jetzt (ein Klick auf
   "Speichern" löschte vorher den API-Key), Sortierung mit fester Spaltenzuordnung,
   Vorschaubilder über `pypdf` mit Datei-Cache.

### Was nicht zurückkommt

Der Code der beiden Juni-Commits selbst ist verloren. Der Nachbau ist an den
Produktionsdaten ausgerichtet (DB-Schema, Scan-State, der alte Thumbnail-Cache mit
seiner 480-px-Kante) und an manchen Stellen besser als das Original — kein
AppleScript-Export mehr, kalibrierte statt geratener Schwelle, `.env`-Merge.

Offen geblieben: der alte Thumbnail-Cache im Ausgabeordner (193 ID-benannte Dateien,
4,9 MB) wird nicht mehr gelesen und kann gelöscht werden.
