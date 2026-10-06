import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string | null): string {
  if (!iso) return "–";
  const d = new Date(iso);
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(-max);
}

/** Nur der Tag, ohne Uhrzeit — fuer Dokumentdaten, die keine Uhrzeit haben.
 *  Ein reines "YYYY-MM-DD" wuerde new Date() als UTC-Mitternacht lesen und in
 *  de-DE als 01:00/02:00 anzeigen; "YYYY-MM" (nur Monat) kann es gar nicht. */
export function formatDay(iso: string | null): string {
  if (!iso) return "–";
  const m = /^(\d{4})-(\d{2})(?:-(\d{2}))?/.exec(iso);
  if (!m) return formatDate(iso);
  const [, y, mo, d] = m;
  return d ? `${d}.${mo}.${y}` : `${mo}/${y}`;
}
