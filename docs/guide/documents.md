# Dokumente

Die Dokumenten-Seite bietet Suche und Filterung ueber alle verarbeiteten Dokumente.

## Volltextsuche

Das Suchfeld nutzt SQLite FTS5 fuer eine schnelle Volltextsuche ueber:

- OCR-Text (der extrahierte Inhalt)
- Dokumenttyp
- Tags
- Vorgeschlagener Dateiname

## Filter

Zwei Dropdown-Menues erlauben zusaetzliche Filterung:

- **Dokumenttyp** — z.B. Rechnung, Vertrag, Brief, Lieferschein
- **Quelle** — Photos oder Email

Filter und Suche koennen kombiniert werden. Der "Zuruecksetzen"-Button entfernt alle Filter.

## Dokumenten-Tabelle

| Spalte | Beschreibung |
|---|---|
| Quelle | Photos oder Email (mit Subject bei E-Mails) |
| Dateiname | Vorgeschlagener Dateiname vom LLM |
| Typ | Dokumenttyp (Rechnung, Vertrag, etc.) |
| Tags | Klickbare Tags (filtern bei Klick) |
| Speicher | Backend (lokal, iCloud, S3) |
| Erstellt | Verarbeitungszeitpunkt |
| Pfad | Speicherpfad oder Cloud-URI |

## OCR-Vorschau

Das Augen-Icon rechts in jeder Zeile oeffnet eine Vorschau des extrahierten OCR-Textes. Nuetzlich, um schnell zu pruefen, ob die Texterkennung korrekt war.

## Pagination

Die Tabelle zeigt maximal 50 Dokumente pro Seite. Mit den Buttons "Zurueck" und "Weiter" kann geblattert werden.
