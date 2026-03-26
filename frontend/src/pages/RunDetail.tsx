import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getRun, getDocuments, type Run, type Document } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { SourceBadge } from "@/components/SourceBadge";
import { StorageBadge } from "@/components/StorageBadge";
import { formatDate } from "@/lib/utils";
import { ArrowLeft, Clock, Camera, FileCheck, AlertTriangle } from "lucide-react";

function InfoItem({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  icon: typeof Clock;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="p-2 rounded-lg bg-muted">
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-medium">{String(value)}</p>
      </div>
    </div>
  );
}

export function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<Run | null>(null);
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const runId = parseInt(id, 10);
    Promise.all([
      getRun(runId),
      getDocuments({ run_id: runId, limit: 200 }),
    ])
      .then(([r, d]) => {
        setRun(r);
        setDocs(d);
      })
      .catch(() => setError("Lauf nicht gefunden"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-muted-foreground">Laden...</div>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive font-medium">{error ?? "Nicht gefunden"}</p>
        <Link to="/" className="text-primary mt-4 inline-block hover:underline">
          Zurueck zum Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link
          to="/"
          className="p-2 rounded-lg hover:bg-muted transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">
              Lauf #{run.id}
            </h1>
            <StatusBadge status={run.status} />
          </div>
        </div>
      </div>

      {/* Run info card */}
      <div className="bg-card rounded-xl border border-border shadow-sm p-6">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
          <InfoItem
            label="Gestartet"
            value={formatDate(run.started_at)}
            icon={Clock}
          />
          <InfoItem
            label="Beendet"
            value={formatDate(run.finished_at)}
            icon={Clock}
          />
          <InfoItem
            label="Fotos gefunden"
            value={run.photos_found}
            icon={Camera}
          />
          <InfoItem
            label="Dokumente"
            value={run.docs_processed}
            icon={FileCheck}
          />
        </div>
        {run.errors > 0 && (
          <div className="mt-4 flex items-center gap-2 text-destructive text-sm">
            <AlertTriangle className="h-4 w-4" />
            {run.errors} Fehler aufgetreten
          </div>
        )}
      </div>

      {/* Log */}
      {run.log && (
        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-border">
            <h2 className="text-base font-semibold">Log-Ausgabe</h2>
          </div>
          <pre className="p-6 text-xs bg-[#1d1d1f] text-gray-300 overflow-auto max-h-80 whitespace-pre-wrap font-mono">
            {run.log}
          </pre>
        </div>
      )}

      {/* Documents */}
      <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-border">
          <h2 className="text-base font-semibold">
            Verarbeitete Dokumente ({docs.length})
          </h2>
        </div>
        {docs.length === 0 ? (
          <div className="px-6 py-8 text-center text-muted-foreground">
            Keine Dokumente in diesem Lauf verarbeitet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    Quelle
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    Dateiname
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    Typ
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    Tags
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    Speicher
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    Pfad
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {docs.map((doc) => (
                  <tr
                    key={doc.id}
                    className="hover:bg-muted/30 transition-colors"
                  >
                    <td className="px-6 py-3">
                      <SourceBadge source={doc.source ?? "photos"} />
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
                          <span
                            key={tag}
                            className="inline-block px-2 py-0.5 rounded-md bg-primary/10 text-primary text-xs"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-3">
                      <StorageBadge backend={doc.storage_backend ?? "local"} />
                    </td>
                    <td className="px-6 py-3 text-xs text-muted-foreground font-mono max-w-[250px] truncate">
                      {doc.cloud_path ?? doc.saved_path ?? "–"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
