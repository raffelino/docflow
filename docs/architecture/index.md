# Architektur-Ueberblick

DocFlow besteht aus einem Python-Backend (FastAPI) und einem React-Frontend (Vite + Tailwind).

## Systemdiagramm

```
┌─────────────────────────────────────────────────┐
│                   DocFlow                        │
│                                                  │
│  ┌──────────────┐     ┌──────────────────────┐  │
│  │  React SPA   │────▶│   FastAPI Backend     │  │
│  │  (Vite)      │ API │                       │  │
│  │              │     │  ┌─────────────────┐  │  │
│  │  Dashboard   │     │  │    Pipeline      │  │  │
│  │  Dokumente   │     │  │                  │  │  │
│  │  Einstellungen│     │  │  OCR → LLM → PDF │  │  │
│  │  Dokumentation│     │  │       ↓          │  │  │
│  └──────────────┘     │  │   Storage → DB   │  │  │
│                       │  └─────────────────┘  │  │
│                       │                       │  │
│                       │  ┌─────────────────┐  │  │
│                       │  │  APScheduler    │  │  │
│                       │  │  (Cron-Job)     │  │  │
│                       │  └─────────────────┘  │  │
│                       └──────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## Technologie-Stack

### Backend

| Technologie | Zweck |
|---|---|
| **Python 3.12+** | Backend-Sprache |
| **FastAPI** | Web-Framework + API |
| **Uvicorn** | ASGI-Server |
| **SQLite + FTS5** | Datenbank + Volltextsuche |
| **APScheduler** | Zeitgesteuerte Pipeline-Ausfuehrung |
| **pydantic-settings** | Konfigurationsmanagement |

### Frontend

| Technologie | Zweck |
|---|---|
| **React 19** | UI-Framework |
| **TypeScript** | Typsicherheit |
| **Vite** | Build-Tool + HMR |
| **Tailwind CSS v4** | Styling |
| **Lucide React** | Icons |
| **React Router v7** | Client-Side Routing |

### Dokumentation

| Technologie | Zweck |
|---|---|
| **VitePress** | Statische Dokumentations-Site |

## Design-Prinzipien

1. **Protocol-basierte Erweiterbarkeit** — LLM-Provider und Storage-Backends sind als Python Protocols definiert
2. **SPA + API Trennung** — Frontend kommuniziert ausschliesslich ueber JSON-APIs
3. **Ein-Port-Architektur** — Gebautes Frontend wird von FastAPI als Static Files serviert
4. **Graceful Degradation** — macOS-spezifische Abhaengigkeiten sind optional
