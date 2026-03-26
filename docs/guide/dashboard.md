# Dashboard

Das Dashboard ist die Startseite der DocFlow Web-UI und zeigt eine Uebersicht aller Pipeline-Laeufe.

## Statistik-Karten

Vier Karten zeigen auf einen Blick:

- **Letzter Lauf** — Zeitpunkt des letzten Pipeline-Durchlaufs
- **Dokumente gesamt** — Anzahl aller verarbeiteten Dokumente
- **Fehler gesamt** — Summe aller Fehler ueber alle Laeufe
- **Fotos verarbeitet** — Anzahl der verarbeiteten Fotos

## Laeufe-Tabelle

Die Tabelle zeigt die letzten 10 Pipeline-Laeufe mit:

| Spalte | Beschreibung |
|---|---|
| ID | Fortlaufende Lauf-Nummer |
| Gestartet | Startzeitpunkt |
| Beendet | Endzeitpunkt |
| Status | Erfolgreich, Fehler oder Laeuft |
| Fotos | Anzahl gefundener Fotos |
| Dokumente | Erfolgreich verarbeitete Dokumente |
| Fehler | Anzahl aufgetretener Fehler |
| Details | Link zur Detail-Ansicht |

## Pipeline manuell starten

Der Button **"Jetzt ausfuehren"** in der oberen Navigation startet die Pipeline sofort im Hintergrund. Der Status aktualisiert sich beim naechsten Seitenladen.
