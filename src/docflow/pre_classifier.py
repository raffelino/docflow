"""Vorentscheidung vor dem LLM: Dokument, Foto oder Video.

Bei ``PHOTOS_SOURCE=all`` laeuft die Pipeline ueber die gesamte Photos-Library
(~15.900 Aufnahmen). Jede davon durch das LLM zu schicken waere teuer und
sinnlos — die grosse Mehrheit sind gewoehnliche Fotos ohne Text. Dieses Modul
entscheidet allein anhand des OCR-Ergebnisses, was ueberhaupt eine
Klassifikation lohnt.

## Kalibrierung (2026-09-12)

Gemessen an 200 zufaelligen Fotos der echten Library (Apple Vision OCR) gegen
871 bereits klassifizierte Dokumente aus der Produktions-DB:

| Gruppe              |   n | Median Textlaenge | Anteil >= 250 Zeichen |
|---------------------|-----|-------------------|-----------------------|
| Fotos               | 200 |                 0 |                  2,5 % |
| Dokumente (DB)      | 871 |               646 |                100,0 % |

Das kuerzeste echte Dokument hat 256 Zeichen, das 95. Perzentil der Fotos liegt
bei 149. Die Textmenge trennt die beiden Gruppen also fast vollstaendig; eine
Schwelle von 250 Zeichen laesst rund 2,5 % der Fotos durch und verliert praktisch
kein Dokument.

## Bewusst nicht verwendet: Screenshot-Erkennung

Naheliegend waere, iPhone-Screenshots (Statuszeile mit Uhrzeit und LTE/5G)
auszusortieren — 54,6 % der als ``Sonstiges`` abgelegten Eintraege sehen so aus.
Die Messung zeigt aber, dass das Muster auch **36,7 % der echten Dokumente**
trifft: Online-Rechnungen, Tickets und Buchungsbestaetigungen liegen als
Screenshot vor. Als Ausschlusskriterium wuerde es also echte Dokumente
verwerfen, und ein verlorenes Dokument ist teurer als ein unnoetiger
LLM-Aufruf. Aus demselben Grund wird ``Sonstiges`` hier nicht vorweggenommen:
Ob ein textreiches Bild ein brauchbares Dokument ist, entscheidet das LLM.
"""

from __future__ import annotations

import re
from typing import Literal

import structlog

logger = structlog.get_logger(__name__)

MediaClass = Literal["document", "photo", "video"]

# Videos werden vor jedem Exportversuch erkannt: Photos.app startet sonst eine
# Medienkonvertierung, die bei iCloud-only-Videos minutenlang haengen bleibt.
_VIDEO_EXTENSIONS = re.compile(
    r"\.(mov|mp4|m4v|avi|mkv|wmv|flv|webm|mpg|mpeg|m2v|mts|m2ts|3gp|3g2|hevc)$",
    re.IGNORECASE,
)

# Mindestmenge OCR-Text, ab der ein Bild als Dokument gilt (siehe Kalibrierung).
DEFAULT_MIN_CHARS = 250

# Ab dieser Laenge genuegt ein eindeutiger Dokumentbegriff, um trotz kurzem Text
# durchzukommen — bei Fotos schlaegt das nur in 1 % der Faelle an, bringt aber
# knappe Quittungen und Belege mit.
_SHORT_TEXT_FLOOR = 120

_DOCUMENT_TERMS = re.compile(
    r"\b(rechnung|betrag|summe|gesamtbetrag|mwst|ust|umsatzsteuer|iban|bic|"
    r"kundennummer|rechnungsnummer|auftragsnummer|zahlbar|faellig|fällig|"
    r"vertrag|versicherung|beitrag|steuer|bescheid|antrag|quittung|beleg|"
    r"lieferschein|mahnung|gutschrift|invoice|receipt)\b",
    re.IGNORECASE,
)


def is_video(filename: str | None) -> bool:
    """True, wenn der Dateiname auf ein Videoformat zeigt."""
    return bool(_VIDEO_EXTENSIONS.search(filename or ""))


def looks_like_document(ocr_text: str | None, min_chars: int = DEFAULT_MIN_CHARS) -> bool:
    """True, wenn die Textmenge (oder ein klarer Dokumentbegriff) fuer ein Dokument spricht."""
    text = (ocr_text or "").strip()
    if len(text) >= min_chars:
        return True
    if len(text) >= _SHORT_TEXT_FLOOR and _DOCUMENT_TERMS.search(text):
        return True
    return False


def classify_media(
    filename: str | None,
    ocr_text: str | None,
    *,
    min_chars: int = DEFAULT_MIN_CHARS,
    force_document: bool = False,
) -> MediaClass:
    """Entscheidet, ob eine Aufnahme zum LLM geht.

    ``force_document`` kommt aus ``FORCE_DOCUMENT_ALBUMS``: Fuer Alben, die der
    Nutzer selbst als Dokumentenablage pflegt, wird die Heuristik uebersprungen.
    Videos bleiben auch dann aussen vor — dafuer gibt es keinen OCR-Pfad.
    """
    if is_video(filename):
        return "video"
    if force_document:
        return "document"
    return "document" if looks_like_document(ocr_text, min_chars) else "photo"
