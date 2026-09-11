# Verlorener Commit `454580c` — Incremental-Scan-Cutoff in die Iteratoren

**Status:** NICHT anwendbar auf den aktuellen Repo-Stand (`c3857c7`, 2026-03-26).
Setzt die Lazy-Iteratoren aus den verlorenen Juni-Commits voraus
(`iter_all_photos`, `iter_photos_in_album`, `_matches_date_range`, `skip_cloud_only`).
Erst anwenden, wenn diese Infrastruktur wieder existiert.

Rekonstruiert aus dem Sitzungsverlauf vom 2026-09-11. Getestet war der Stand am
2026-09-04 (5 Unit-Tests grün, fünf Produktionsläufe 108–112 fehlerfrei).

## Problem

Der Cutoff für inkrementelle Scans wurde in der Consumer-Schleife von
`Pipeline.run()` geprüft — also *nachdem* der Iterator das Foto schon exportiert
und iCloud-only-Fotos heruntergeladen hatte:

```python
for idx, photo in enumerate(photo_iter, 1):
    # Filter by date_added if incremental scan
    if scan_cutoff and hasattr(photo, "date_added") and photo.date_added is not None and photo.date_added < scan_cutoff:
        continue
```

Zwei Fehler darin:

1. Die teure I/O passiert vor dem Filter.
2. `photo.date_added` ist bei osxphotos **tz-aware**, der Scan-State speichert
   **naive UTC**. Der Vergleich `<` wirft dann `TypeError: can't compare
   offset-naive and offset-aware datetimes`.

## Lösung

Helper in `photos.py` (oberhalb von `_OSXPHOTOS_AVAILABLE`), `timezone` zusätzlich
aus `datetime` importieren:

```python
def _added_before_cutoff(date_added: datetime | None, cutoff: datetime | None) -> bool:
    """True if a photo was added before the incremental scan cutoff.

    Normalises both sides to naive UTC so tz-aware (osxphotos) and naive
    (scan-state) timestamps compare without raising.
    """
    if date_added is None or cutoff is None:
        return False

    def _utc_naive(dt: datetime) -> datetime:
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    return _utc_naive(date_added) < _utc_naive(cutoff)
```

`PhotoInfo` bekommt `date_added: datetime | None = field(default=None)`, und
`date_added=getattr(p, "date_added", None)` muss an **jeder** Yield-Stelle
mitgegeben werden — auch im Video-Zweig, im `ismissing`-Zweig und in beiden
Zweigen des iCloud-Downloads.

Beide Iteratoren (`iter_all_photos`, `iter_photos_in_album`) sowie die
`MockPhotosLibrary`-Pendants bekommen `scan_cutoff: datetime | None = None` und
direkt nach der Datumsbereichsprüfung:

```python
# Incremental: skip already-scanned photos before export/download
if _added_before_cutoff(getattr(p, "date_added", None), scan_cutoff):
    continue
```

In `MockPhotosLibrary` heißt es `p.date_added` statt `getattr(...)`, und
`iter_all_photos` muss `scan_cutoff` an `iter_photos_in_album` weiterreichen.

In `pipeline.py` wird der Filter aus der Schleife entfernt und stattdessen
`scan_cutoff=scan_cutoff` an beide Iterator-Aufrufe übergeben, mit Notiz:

```python
# Note: the incremental cutoff is applied inside the iterator (before
# any export/download), so no further date_added check is needed here.
```

## Tests

`tests/unit/test_scan_cutoff.py`, 5 Tests: None-Eingaben filtern nie; naive
Vergleiche vor/nach dem Cutoff; tz-aware `date_added` gegen naiven Cutoff wirft
nicht mehr (`2026-06-09 23:00+02:00` == `21:00 UTC` → vor `2026-06-10 00:00`,
`2026-06-10 05:00+02:00` == `03:00 UTC` → danach); Mock-Iterator überspringt alte
Fotos; ohne Cutoff kommen alle durch.
