import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getRuns, type Run } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDate } from "@/lib/utils";
import {
  ArrowRight,
  Activity,
  FileCheck,
  AlertTriangle,
  Camera,
} from "lucide-react";

function StatCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string | number;
  icon: typeof Activity;
  color: string;
}) {
  return (
    <div className="bg-card rounded-xl border border-border p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold mt-1">{value}</p>
        </div>
        <div className={`p-3 rounded-lg ${color}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRuns(10)
      .then(setRuns)
      .finally(() => setLoading(false));
  }, []);

  const lastRun = runs[0];
  const totalDocs = runs.reduce((s, r) => s + r.docs_processed, 0);
  const totalErrors = runs.reduce((s, r) => s + r.errors, 0);
  const totalPhotos = runs.reduce((s, r) => s + r.photos_found, 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-muted-foreground">Laden...</div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Uebersicht der letzten Pipeline-Laeufe
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Letzter Lauf"
          value={lastRun ? formatDate(lastRun.started_at) : "–"}
          icon={Activity}
          color="bg-primary/10 text-primary"
        />
        <StatCard
          label="Dokumente gesamt"
          value={totalDocs}
          icon={FileCheck}
          color="bg-success/10 text-success"
        />
        <StatCard
          label="Fehler gesamt"
          value={totalErrors}
          icon={AlertTriangle}
          color="bg-destructive/10 text-destructive"
        />
        <StatCard
          label="Fotos verarbeitet"
          value={totalPhotos}
          icon={Camera}
          color="bg-blue-100 text-blue-600"
        />
      </div>

      <div className="bg-card rounded-xl border border-border shadow-sm">
        <div className="px-6 py-4 border-b border-border">
          <h2 className="text-base font-semibold">Letzte Laeufe</h2>
        </div>
        {runs.length === 0 ? (
          <div className="px-6 py-12 text-center text-muted-foreground">
            Noch keine Pipeline-Laeufe vorhanden. Klicke oben auf "Jetzt
            ausfuehren" um den ersten Lauf zu starten.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    ID
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    Gestartet
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    Beendet
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    Status
                  </th>
                  <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                    Fotos
                  </th>
                  <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                    Dokumente
                  </th>
                  <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                    Fehler
                  </th>
                  <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                    Details
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {runs.map((run) => (
                  <tr
                    key={run.id}
                    className="hover:bg-muted/30 transition-colors"
                  >
                    <td className="px-6 py-3 font-mono text-xs text-muted-foreground">
                      #{run.id}
                    </td>
                    <td className="px-6 py-3">
                      {formatDate(run.started_at)}
                    </td>
                    <td className="px-6 py-3">
                      {formatDate(run.finished_at)}
                    </td>
                    <td className="px-6 py-3">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="px-6 py-3 text-right tabular-nums">
                      {run.photos_found}
                    </td>
                    <td className="px-6 py-3 text-right tabular-nums font-medium">
                      {run.docs_processed}
                    </td>
                    <td className="px-6 py-3 text-right tabular-nums">
                      {run.errors > 0 ? (
                        <span className="text-destructive font-medium">
                          {run.errors}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">0</span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-right">
                      <Link
                        to={`/runs/${run.id}`}
                        className="inline-flex items-center gap-1 text-primary hover:text-primary/80 font-medium transition-colors"
                      >
                        Ansehen
                        <ArrowRight className="h-3.5 w-3.5" />
                      </Link>
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
