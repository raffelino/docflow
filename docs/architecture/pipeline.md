# Pipeline-Architektur

## Ablauf

```
Pipeline.run()
    │
    ├─ 1. db.create_run() → run_id
    │
    ├─ 2. Photos-Phase
    │     ├─ get_library() → PhotosLibrary
    │     ├─ get_photos_in_album() → [PhotoInfo]
    │     └─ Fuer jedes Photo:
    │         ├─ ocr.extract_text(path) → text
    │         ├─ llm.classify_document(text) → Classification
    │         ├─ _image_to_pdf_bytes(path) → bytes
    │         ├─ storage.save(pdf, "YYYY/MM/name.pdf") → saved_path
    │         └─ db.insert_document(...)
    │
    ├─ 3. Email-Phase (wenn enabled)
    │     ├─ IMAPEmailSource.fetch_attachments() → [Attachment]
    │     └─ Fuer jeden Anhang:
    │         ├─ extract_text_from_attachment() → text
    │         ├─ llm.classify_document(text) → Classification
    │         ├─ PDF erstellen/kopieren → bytes
    │         ├─ storage.save(...) → saved_path
    │         ├─ db.insert_document(..., source="email")
    │         └─ _move_message(processed_folder)
    │
    └─ 4. db.finish_run(run_id, status, counts, log)
```

## Fehlerbehandlung

- **Pro-Dokument**: Fehler werden gefangen und geloggt, die Pipeline laeuft weiter
- **Run-Status**: `success` wenn mindestens ein Dokument verarbeitet, `error` bei Totalausfall
- **Log**: Alle Events und Fehler werden im Run-Log gespeichert

## Dateipfad-Struktur

PDFs werden nach diesem Schema abgelegt:

```
{output_dir}/
└── 2026/
    └── 03/
        ├── 2026-03-15_Vodafone_Rechnung.pdf
        ├── 2026-03-20_Allianz_Vertrag.pdf
        └── 2026-03-23_Amazon_Lieferschein.pdf
```

## Hilfsfunktionen

- `_safe_filename(name)` — Entfernt unsichere Zeichen, kuerzt auf 200 Zeichen
- `_destination_path(filename, created_at)` — Baut `YYYY/MM/filename.pdf`
- `_image_to_pdf_bytes(path)` — Konvertiert Bild zu PDF (img2pdf mit Pillow-Fallback)
