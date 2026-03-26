# API Referenz

DocFlow stellt eine JSON REST API bereit. Alle Endpoints sind unter `/api/` erreichbar.

## Uebersicht

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/runs` | Pipeline-Laeufe auflisten |
| GET | `/api/runs/:id` | Einzelnen Lauf abrufen |
| GET | `/api/documents` | Dokumente suchen/filtern |
| GET | `/api/documents/:id` | Einzelnes Dokument abrufen |
| GET | `/api/doc-types` | Verfuegbare Dokumenttypen |
| GET | `/api/settings` | Aktuelle Einstellungen |
| POST | `/api/settings` | Einstellungen aktualisieren |
| POST | `/runs/trigger` | Pipeline manuell starten |

## Authentifizierung

Aktuell keine Authentifizierung erforderlich. Die API ist nur im lokalen Netzwerk verfuegbar.

::: warning Sicherheitshinweis
Wenn `WEB_HOST=0.0.0.0` gesetzt ist, ist die API fuer alle Geraete im Netzwerk erreichbar. Secrets (API-Keys, Passwoerter) werden nie ueber die API exponiert.
:::
