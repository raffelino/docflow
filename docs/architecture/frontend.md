# Frontend-Architektur

## Verzeichnisstruktur

```
frontend/
├── src/
│   ├── main.tsx              # Entry mit BrowserRouter
│   ├── App.tsx               # Route-Definitionen
│   ├── lib/
│   │   ├── api.ts            # Typisierter API-Client
│   │   └── utils.ts          # Hilfsfunktionen
│   ├── components/
│   │   ├── Layout.tsx        # Navigation + Outlet
│   │   ├── StatusBadge.tsx   # Run-Status Badges
│   │   ├── SourceBadge.tsx   # Photos/Email Badges
│   │   └── StorageBadge.tsx  # Storage-Backend Badges
│   └── pages/
│       ├── Dashboard.tsx     # Stats + Runs-Tabelle
│       ├── Documents.tsx     # Suche + Dokumenten-Tabelle
│       ├── RunDetail.tsx     # Einzelner Lauf
│       ├── Settings.tsx      # Konfiguration
│       └── Docs.tsx          # Dokumentations-Link
├── vite.config.ts            # Build + API-Proxy
└── package.json
```

## Design-System

### Farben

| Rolle | Wert | Verwendung |
|---|---|---|
| Primary | `hsl(211 100% 45%)` | Buttons, Links, Akzente |
| Background | `hsl(0 0% 98%)` | Seitenhintergrund |
| Card | `hsl(0 0% 100%)` | Karten, Tabellen |
| Muted | `hsl(0 0% 96%)` | Dezente Hintergruende |
| Success | `hsl(142 71% 45%)` | Erfolgs-Status |
| Destructive | `hsl(0 84% 60%)` | Fehler-Status |
| Warning | `hsl(38 92% 50%)` | Laufend-Status |

### Typografie

System-Fonts: `-apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto`

### Komponenten

- **StatusBadge** — Farbkodiert mit Icon (Erfolg/Fehler/Laeuft)
- **SourceBadge** — Photos (blau) oder Email (lila)
- **StorageBadge** — Lokal (grau), iCloud (cyan), S3 (orange)

## API-Client

Der API-Client in `lib/api.ts` bietet typisierte Funktionen:

```typescript
getRuns(limit?: number): Promise<Run[]>
getRun(id: number): Promise<Run>
getDocuments(params): Promise<Document[]>
getDocTypes(): Promise<string[]>
getSettings(): Promise<Settings>
saveSettings(data: Settings): Promise<void>
triggerRun(): Promise<void>
```

## SPA-Integration

In Produktion wird das gebaute Frontend (`frontend/dist/`) nach `src/docflow/web/static/` kopiert. FastAPI serviert die Static Files und leitet alle nicht-API-Routen an `index.html` weiter (SPA-Fallback).

In der Entwicklung laeuft Vite auf Port 5173 und leitet `/api/*` an FastAPI (Port 8765) weiter.
