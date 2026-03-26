# Documents API

## Dokumente suchen und filtern

```http
GET /api/documents?q=Vodafone&doc_type=Rechnung&source=photos&run_id=9&limit=50&offset=0
```

**Parameter:**
- `q` (optional) — Volltextsuche (FTS5)
- `doc_type` (optional) — Nach Dokumenttyp filtern
- `source` (optional) — `photos` oder `email`
- `run_id` (optional) — Nach Pipeline-Lauf filtern
- `limit` (optional, default: 50) — Maximale Anzahl
- `offset` (optional, default: 0) — Offset fuer Pagination

**Response:**
```json
[
  {
    "id": 1,
    "run_id": 9,
    "original_filename": "IMG_1234.jpeg",
    "ocr_text": "Vodafone Rechnung März 2026...",
    "doc_type": "Rechnung",
    "tags": "[\"Vodafone\", \"Mobilfunk\"]",
    "tags_list": ["Vodafone", "Mobilfunk"],
    "suggested_filename": "2026-03_Vodafone_Rechnung.pdf",
    "saved_path": "/Users/.../output/2026/03/2026-03_Vodafone_Rechnung.pdf",
    "created_at": "2026-03-23T21:17:26.000000",
    "source": "photos",
    "storage_backend": "local",
    "cloud_path": null
  }
]
```

## Einzelnes Dokument abrufen

```http
GET /api/documents/:id
```

**Response:** Einzelnes Dokument-Objekt oder `404`.

## Dokumenttypen auflisten

```http
GET /api/doc-types
```

**Response:**
```json
["Rechnung", "Vertrag", "Lieferschein", "Brief", "Sonstiges"]
```
