"""Dokumentdatum bestimmen: LLM-Vorschlag pruefen, sonst Fotodatum.

Das LLM nennt ein Datum (``document_date``) und sagt, wie es dazu kommt
(``date_kind``). Uebernommen wird es nur, wenn drei Dinge zusammenkommen:

1. ``date_kind == "explicit"`` — es ist das Datum *des Dokuments* (Rechnungs-,
   Brief-, Kassenbon-Datum), nicht irgendein Datum im Text (Geburtsdatum,
   Gueltig-bis, Veranstaltungstermin).
2. Das Datum steht **woertlich im OCR-Text**. Das ist der wirksamste Schutz
   gegen Halluzination: 56 % der Altbestaende tragen 2023-03 bis 2023-05 im
   Dateinamen — das „heute" von Claude 3 Haiku, nicht das Dokumentdatum.
3. Es ist plausibel: nicht vor 1990 und hoechstens ein Jahr nach dem Fotodatum
   (Tickets duerfen in der Zukunft liegen, aber nicht beliebig).

Sonst gilt das Fotodatum. Beides wird gespeichert, damit die UI zeigen kann,
woher ein Datum stammt, und nach beidem sortieren kann.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

MIN_YEAR = 1990
# Wie weit darf ein Dokumentdatum nach dem Fotodatum liegen? Konzert-Tickets
# und Terminbestaetigungen nennen Daten in der Zukunft, Jahre weit aber nie.
MAX_FUTURE = timedelta(days=366)

MONATE = {
    1: ("januar", "jan", "jänner", "jaenner"),
    2: ("februar", "feb"),
    3: ("märz", "maerz", "mär", "mrz"),
    4: ("april", "apr"),
    5: ("mai",),
    6: ("juni", "jun"),
    7: ("juli", "jul"),
    8: ("august", "aug"),
    9: ("september", "sep", "sept"),
    10: ("oktober", "okt"),
    11: ("november", "nov"),
    12: ("dezember", "dez"),
}
# Englische Namen fuer Online-Rechnungen und Tickets
MONATE_EN = {
    1: ("january",), 2: ("february",), 3: ("march", "mar"), 4: ("april",),
    5: ("may",), 6: ("june",), 7: ("july",), 8: ("august",),
    9: ("september",), 10: ("october", "oct"), 11: ("november",), 12: ("december", "dec"),
}


@dataclass(frozen=True)
class ParsedDate:
    """Ein vom LLM genanntes Datum; ``month_only`` wenn nur Monat und Jahr."""

    value: date
    month_only: bool = False

    @property
    def iso(self) -> str:
        return self.value.strftime("%Y-%m") if self.month_only else self.value.isoformat()


@dataclass(frozen=True)
class DateResolution:
    """Ergebnis der Datumsbestimmung fuer ein Dokument."""

    # Das akzeptierte Dokumentdatum (None, wenn keines bestanden hat)
    document_date: ParsedDate | None
    # Das Datum, nach dem abgelegt und sortiert wird
    effective_date: date | None
    # 'document' | 'photo' | 'none'
    source: str
    # Kurze Begruendung fuers Lauf-Log
    reason: str

    @property
    def document_date_iso(self) -> str | None:
        return self.document_date.iso if self.document_date else None

    @property
    def effective_date_iso(self) -> str | None:
        return self.effective_date.isoformat() if self.effective_date else None


def parse_llm_date(raw: object) -> ParsedDate | None:
    """``YYYY-MM-DD`` oder ``YYYY-MM`` aus der LLM-Antwort lesen, sonst None."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() in {"null", "none", "unknown", "unbekannt", ""}:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", s)
    if not m:
        return None
    jahr, monat, tag = int(m.group(1)), int(m.group(2)), m.group(3)
    try:
        if tag is None:
            return ParsedDate(date(jahr, monat, 1), month_only=True)
        return ParsedDate(date(jahr, monat, int(tag)))
    except ValueError:
        return None


def _month_names(monat: int) -> list[str]:
    return [*MONATE[monat], *MONATE_EN[monat]]


def _date_patterns(d: ParsedDate) -> list[str]:
    """Regex-Varianten, in denen das Datum in OCR-Text stehen kann."""
    y = d.value.year
    yy = f"{y % 100:02d}"
    m = d.value.month
    mm = f"{m:02d}"
    namen = "|".join(re.escape(n) for n in _month_names(m))
    # OCR laesst Leerzeichen um Punkte gern weg oder fuegt sie ein
    sp = r"\s*"
    patterns: list[str] = []

    if not d.month_only:
        t = d.value.day
        tt = f"{t:02d}"
        tag_alt = f"(?:{tt}|{t})"
        monat_alt = f"(?:{mm}|{m})"
        patterns += [
            # 13.05.2024, 13.5.2024, 13.05.24
            rf"(?<!\d){tag_alt}{sp}\.{sp}{monat_alt}{sp}\.{sp}(?:{y}|{yy})(?!\d)",
            # 2024-05-13
            rf"(?<!\d){y}-{mm}-{tt}(?!\d)",
            # 13/05/2024, 05/13/2024 (US)
            rf"(?<!\d){tag_alt}/{monat_alt}/(?:{y}|{yy})(?!\d)",
            rf"(?<!\d){monat_alt}/{tag_alt}/(?:{y}|{yy})(?!\d)",
            # 13. Mai 2024, 13 Mai 2024, 13.Mai 2024
            rf"(?<!\d){tag_alt}{sp}\.?{sp}(?:{namen})\.?{sp}{y}(?!\d)",
            # May 13, 2024
            rf"(?:{namen})\.?{sp}{tag_alt},?{sp}{y}(?!\d)",
        ]
    else:
        monat_alt = f"(?:{mm}|{m})"
        patterns += [
            # Mai 2024, Mai/2024
            rf"(?:{namen})\.?{sp}/?{sp}{y}(?!\d)",
            # 05/2024, 05.2024, 05-2024 — auch mit Tag davor (13.05.2024).
            # Nur vierstellige Jahre: "5.24" waere sonst auch ein Betrag.
            rf"(?<!\d){monat_alt}{sp}[./-]{sp}{y}(?!\d)",
            # 2024-05, 2024-05-13
            rf"(?<!\d){y}-{mm}(?!\d)",
        ]
    return patterns


def date_in_text(d: ParsedDate, text: str) -> bool:
    """Steht das Datum in einer der ueblichen Schreibweisen im Text?"""
    if not text:
        return False
    for pattern in _date_patterns(d):
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True
    return False


def is_plausible(d: ParsedDate, photo_date: date | datetime | None) -> bool:
    """Weder aus den 80ern noch Jahre in der Zukunft."""
    if d.value.year < MIN_YEAR:
        return False
    bezug = _as_date(photo_date) or date.today()
    return d.value <= bezug + MAX_FUTURE


def _as_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def resolve_document_date(
    llm_date: object,
    date_kind: str | None,
    ocr_text: str,
    photo_date: date | datetime | None,
) -> DateResolution:
    """LLM-Datum pruefen und das wirksame Datum festlegen.

    ``photo_date`` ist das Aufnahmedatum (bei Mail-Anhaengen das Mail-Datum).
    """
    fallback = _as_date(photo_date)
    fallback_source = "photo" if fallback else "none"

    def ablehnen(grund: str) -> DateResolution:
        return DateResolution(None, fallback, fallback_source, grund)

    parsed = parse_llm_date(llm_date)
    if parsed is None:
        return ablehnen("kein Dokumentdatum erkannt")
    kind = (date_kind or "").strip().lower()
    if kind != "explicit":
        return ablehnen(f"LLM-Datum {parsed.iso} nicht als Dokumentdatum markiert ({kind or 'ohne Art'})")
    if not date_in_text(parsed, ocr_text):
        return ablehnen(f"LLM-Datum {parsed.iso} nicht im OCR-Text gefunden")
    if not is_plausible(parsed, photo_date):
        return ablehnen(f"LLM-Datum {parsed.iso} unplausibel (Fotodatum {fallback})")
    return DateResolution(parsed, parsed.value, "document", f"Dokumentdatum {parsed.iso} im Text bestaetigt")


_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}(?:-\d{2})?[_\-\s]+")


def strip_date_prefix(filename: str) -> str:
    """Ein vom LLM vorangestelltes ``YYYY-MM_`` entfernen — den Praefix baut der Code."""
    return _DATE_PREFIX.sub("", filename.strip()) or filename.strip()


def apply_date_prefix(filename: str, datum: date | datetime | None) -> str:
    """Dateiname mit ``YYYY-MM_`` aus dem wirksamen Datum (ohne Datum: unveraendert)."""
    rest = strip_date_prefix(filename)
    d = _as_date(datum)
    if d is None:
        return rest
    return f"{d.strftime('%Y-%m')}_{rest}"
