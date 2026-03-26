# Installation

## Backend

### Mit uv (empfohlen)

```bash
# Abhaengigkeiten installieren
uv sync --dev

# macOS-spezifische Extras (osxphotos + pyobjc)
uv sync --extra macos
```

### Konfiguration

Erstelle eine `.env`-Datei im Projektverzeichnis:

```bash
cp .env.example .env
```

Mindestens noetig:
- `LLM_PROVIDER` und der zugehoerige API-Key
- `PHOTOS_ALBUM` (Name des Albums in Apple Photos)

### Server starten

```bash
uv run python -m docflow
```

Der Server startet auf `http://127.0.0.1:8765`.

Fuer Zugriff von anderen Geraeten im Netzwerk:

```bash
# In .env setzen:
WEB_HOST=0.0.0.0
```

## Frontend (Entwicklung)

Das Frontend ist bereits vorgebaut im Python-Package enthalten. Fuer Entwicklung:

```bash
cd frontend
npm install
npm run dev
```

Der Vite Dev-Server startet auf Port 5173 und leitet API-Aufrufe an Port 8765 weiter.

### Frontend bauen und deployen

```bash
./scripts/build_frontend.sh
```

Dies baut das React-Frontend und kopiert es nach `src/docflow/web/static/`.
