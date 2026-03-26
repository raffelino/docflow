# Ueberblick

DocFlow ist eine automatisierte Dokumentenverarbeitungs-Pipeline fuer macOS. Sie nimmt Fotos aus Apple Photos und E-Mail-Anhaenge entgegen, extrahiert Text per OCR, klassifiziert Dokumente mittels KI und archiviert sie als durchsuchbare PDFs.

## Was DocFlow macht

```
Foto/E-Mail → OCR → KI-Klassifikation → PDF → Archiv → Durchsuchbar
```

### Schritt fuer Schritt

1. **Eingabe**: Fotos aus einem Apple Photos Album oder E-Mail-Anhaenge via IMAP
2. **OCR**: Apple Vision Framework extrahiert den Text aus dem Bild
3. **Klassifikation**: Ein LLM (Anthropic Claude, Ollama oder OpenRouter) erkennt den Dokumenttyp und vergibt Tags
4. **PDF-Erstellung**: Das Foto wird in ein PDF konvertiert
5. **Speicherung**: Das PDF wird im konfigurierten Backend abgelegt (lokal, iCloud, S3)
6. **Indexierung**: Alle Metadaten landen in einer SQLite-Datenbank mit Volltextsuche

## Systemvoraussetzungen

| Komponente | Voraussetzung |
|---|---|
| Betriebssystem | macOS 13+ (Ventura oder neuer) |
| Python | 3.12+ |
| Node.js | 18+ (nur fuer Frontend-Entwicklung) |
| Apple Photos | Fuer Foto-Eingang |
| LLM-Zugang | Anthropic API-Key, Ollama (lokal) oder OpenRouter |

## Schnellstart

```bash
# Repository klonen
git clone <repo-url>
cd docflow

# Backend installieren
uv sync --dev --extra macos

# Server starten
uv run python -m docflow

# Browser oeffnen
open http://localhost:8765
```

Das Dashboard zeigt sofort den Status. Klicke **"Jetzt ausfuehren"** um die erste Pipeline zu starten.
