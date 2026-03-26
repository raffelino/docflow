# Settings API

## Einstellungen abrufen

```http
GET /api/settings
```

**Response:**
```json
{
  "photos_source": "album",
  "photos_album": "Dokumente",
  "llm_provider": "anthropic",
  "ollama_base_url": "http://localhost:11434",
  "ollama_model": "llama3.2",
  "openrouter_model": "anthropic/claude-3-haiku",
  "storage_backend": "local",
  "output_dir": "/Users/.../output",
  "schedule_hour": "2",
  "schedule_minute": "0",
  "email_enabled": "False",
  "web_host": "0.0.0.0",
  "web_port": "8765"
}
```

::: info Keine Secrets
API-Keys und Passwoerter werden **nicht** in der Response zurueckgegeben.
:::

## Einstellungen aktualisieren

```http
POST /api/settings
Content-Type: application/json

{
  "photos_album": "MeinAlbum",
  "llm_provider": "ollama",
  "schedule_hour": "3"
}
```

Es muessen nur die zu aendernden Felder gesendet werden. Die Aenderungen werden sofort in-memory angewendet und in die `.env`-Datei geschrieben.

**Response:**
```json
{ "status": "ok" }
```
