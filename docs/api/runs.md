# Runs API

## Laeufe auflisten

```http
GET /api/runs?limit=10
```

**Parameter:**
- `limit` (optional, default: 10) — Maximale Anzahl

**Response:**
```json
[
  {
    "id": 9,
    "started_at": "2026-03-23T21:17:16.828603",
    "finished_at": "2026-03-23T21:17:27.385777",
    "status": "success",
    "photos_found": 2,
    "docs_processed": 2,
    "errors": 0,
    "log": "[2026-03-23T21:17:16] Pipeline started..."
  }
]
```

## Einzelnen Lauf abrufen

```http
GET /api/runs/:id
```

**Response:** Einzelnes Run-Objekt (wie oben) oder `404`.

## Pipeline manuell starten

```http
POST /runs/trigger
```

Startet die Pipeline im Hintergrund. Gibt `303 Redirect` zurueck.
