import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { getDocuments, getDocTypes, thumbnailUrl, type Document } from "@/lib/api";
import { SourceBadge } from "@/components/SourceBadge";
import { StorageBadge } from "@/components/StorageBadge";
import { formatDate, truncate } from "@/lib/utils";
import { Search, X, ChevronLeft, ChevronRight, Eye, ArrowUp, ArrowDown,
  FileText } from "lucide-react";

const LIMIT = 50;

/** Vorschaubild mit Platzhalter.
 *
 *  Der Endpoint antwortet mit 404, wenn keine Datei vorliegt (aussortierte
 *  Fotos und Videos haben keinen saved_path) oder sich kein Bild extrahieren
 *  laesst. Statt eines kaputten Bildsymbols wird dann ein Platzhalter gezeigt.
 */
function DocThumb({ doc }: { doc: Document }) {
  const [fehler, setFehler] = useState(false);

  if (!doc.saved_path || fehler) {
    return (
      <div
        className="h-12 w-12 rounded-md bg-muted flex items-center justify-center"
        title="Keine Vorschau"
      >
        <FileText className="h-5 w-5 text-muted-foreground" />
      </div>
    );
  }

  return (
    <img
      src={thumbnailUrl(doc.id, 96)}
      alt=""
      loading="lazy"
      onError={() => setFehler(true)}
      className="h-12 w-12 rounded-md object-cover border border-border bg-muted"
    />
  );
}

export function DocumentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [docs, setDocs] = useState<Document[]>([]);
  const [docTypes, setDocTypes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);

  const q = searchParams.get("q") ?? "";
  const docType = searchParams.get("doc_type") ?? "";
  const source = searchParams.get("source") ?? "";
  const offset = parseInt(searchParams.get("offset") ?? "0", 10);
  const sort = searchParams.get("sort") ?? "created_at";
  const order = (searchParams.get("order") ?? "desc") as "asc" | "desc";

  const fetchDocs = useCallback(() => {
    setLoading(true);
    getDocuments({
      q: q || undefined,
      doc_type: docType || undefined,
      source: source || undefined,
      limit: LIMIT,
      offset,
      sort,
      order,
    })
      .then(setDocs)
      .finally(() => setLoading(false));
  }, [q, docType, source, offset, sort, order]);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  useEffect(() => {
    getDocTypes().then(setDocTypes).catch(() => {});
  }, []);

  const updateParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    next.delete("offset");
    setSearchParams(next);
  };

  const toggleSort = (feld: string) => {
    const next = new URLSearchParams(searchParams);
    if (sort === feld) {
      next.set("order", order === "asc" ? "desc" : "asc");
    } else {
      next.set("sort", feld);
      next.set("order", "desc");
    }
    next.delete("offset");
    setSearchParams(next);
  };

  // Die Volltextsuche sortiert nach Relevanz — dann sind Spaltenkoepfe inaktiv.
  const sortierbar = !q;

  const SortHeader = ({ feld, children }: { feld: string; children: React.ReactNode }) => {
    if (!sortierbar) {
      return (
        <th className="px-6 py-3 text-left font-medium text-muted-foreground">
          {children}
        </th>
      );
    }
    const aktiv = sort === feld;
    return (
      <th className="px-6 py-3 text-left font-medium text-muted-foreground">
        <button
          type="button"
          onClick={() => toggleSort(feld)}
          className="inline-flex items-center gap-1 hover:text-foreground transition-colors"
          aria-sort={aktiv ? (order === "asc" ? "ascending" : "descending") : "none"}
        >
          {children}
          {aktiv &&
            (order === "asc" ? (
              <ArrowUp className="h-3 w-3" />
            ) : (
              <ArrowDown className="h-3 w-3" />
            ))}
        </button>
      </th>
    );
  };

  const clearFilters = () => setSearchParams({});

  const hasFilters = q || docType || source;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dokumente</h1>
        <p className="text-muted-foreground mt-1">
          Suche und filtere verarbeitete Dokumente
        </p>
      </div>

      {/* Search & Filters */}
      <div className="bg-card rounded-xl border border-border shadow-sm p-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Volltextsuche..."
              value={q}
              onChange={(e) => updateParam("q", e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && fetchDocs()}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <select
            value={docType}
            onChange={(e) => updateParam("doc_type", e.target.value)}
            className="px-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">Alle Typen</option>
            {docTypes.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <select
            value={source}
            onChange={(e) => updateParam("source", e.target.value)}
            className="px-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">Alle Quellen</option>
            <option value="photos">Photos</option>
            <option value="email">Email</option>
          </select>
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <X className="h-4 w-4" />
              Zuruecksetzen
            </button>
          )}
        </div>
      </div>

      {/* Documents table */}
      <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
        {loading ? (
          <div className="px-6 py-12 text-center text-muted-foreground animate-pulse">
            Laden...
          </div>
        ) : docs.length === 0 ? (
          <div className="px-6 py-12 text-center text-muted-foreground">
            {hasFilters
              ? "Keine Dokumente fuer diese Filterkriterien gefunden."
              : "Noch keine Dokumente vorhanden."}
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th className="px-6 py-3 w-16 text-left font-medium text-muted-foreground">
                      Vorschau
                    </th>
                    <SortHeader feld="source">Quelle</SortHeader>
                    <SortHeader feld="filename">Dateiname</SortHeader>
                    <SortHeader feld="doc_type">Typ</SortHeader>
                    <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                      Tags
                    </th>
                    <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                      Speicher
                    </th>
                    <SortHeader feld="created_at">Erstellt</SortHeader>
                    <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                      Pfad
                    </th>
                    <th className="px-6 py-3 w-10"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {docs.map((doc) => (
                    <tr
                      key={doc.id}
                      className="hover:bg-muted/30 transition-colors group"
                    >
                      <td className="px-6 py-3">
                        <DocThumb doc={doc} />
                      </td>
                      <td className="px-6 py-3">
                        <SourceBadge source={doc.source ?? "photos"} />
                        {doc.email_subject && (
                          <p className="text-xs text-muted-foreground mt-1 max-w-[180px] truncate">
                            {doc.email_subject}
                          </p>
                        )}
                      </td>
                      <td className="px-6 py-3 font-medium">
                        {doc.saved_path ? (
                          <a
                            href={`/api/documents/${doc.id}/file`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline"
                          >
                            {doc.suggested_filename || doc.original_filename}
                          </a>
                        ) : (
                          doc.suggested_filename || doc.original_filename
                        )}
                      </td>
                      <td className="px-6 py-3">
                        <span className="inline-block px-2 py-0.5 rounded-md bg-muted text-xs font-medium">
                          {doc.doc_type}
                        </span>
                      </td>
                      <td className="px-6 py-3">
                        <div className="flex flex-wrap gap-1">
                          {doc.tags_list.map((tag) => (
                            <button
                              key={tag}
                              onClick={() => updateParam("q", tag)}
                              className="inline-block px-2 py-0.5 rounded-md bg-primary/10 text-primary text-xs hover:bg-primary/20 transition-colors cursor-pointer"
                            >
                              {tag}
                            </button>
                          ))}
                        </div>
                      </td>
                      <td className="px-6 py-3">
                        <StorageBadge
                          backend={doc.storage_backend ?? "local"}
                        />
                      </td>
                      <td className="px-6 py-3 text-muted-foreground">
                        {formatDate(doc.created_at)}
                      </td>
                      <td className="px-6 py-3 text-xs text-muted-foreground font-mono max-w-[200px] truncate">
                        {truncate(
                          doc.cloud_path ?? doc.saved_path ?? "",
                          60,
                        )}
                      </td>
                      <td className="px-6 py-3">
                        <button
                          onClick={() =>
                            setExpanded(expanded === doc.id ? null : doc.id)
                          }
                          className="p-1 rounded hover:bg-muted transition-colors opacity-0 group-hover:opacity-100"
                          title="OCR-Text anzeigen"
                        >
                          <Eye className="h-4 w-4 text-muted-foreground" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Expanded OCR preview */}
            {expanded !== null && (
              <div className="border-t border-border px-6 py-4 bg-muted/30">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium">OCR-Text Vorschau</h3>
                  <button
                    onClick={() => setExpanded(null)}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <pre className="text-xs bg-[#1d1d1f] text-gray-300 rounded-lg p-4 max-h-48 overflow-auto whitespace-pre-wrap font-mono">
                  {docs.find((d) => d.id === expanded)?.ocr_text ||
                    "(kein OCR-Text)"}
                </pre>
              </div>
            )}

            {/* Pagination */}
            <div className="flex items-center justify-between px-6 py-3 border-t border-border">
              <span className="text-sm text-muted-foreground">
                {docs.length} Dokumente angezeigt
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() =>
                    updateParam(
                      "offset",
                      String(Math.max(0, offset - LIMIT)),
                    )
                  }
                  disabled={offset === 0}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-input text-sm hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Zurueck
                </button>
                <button
                  onClick={() =>
                    updateParam("offset", String(offset + LIMIT))
                  }
                  disabled={docs.length < LIMIT}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-input text-sm hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Weiter
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
