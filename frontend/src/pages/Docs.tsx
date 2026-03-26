import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import Markdown from "react-markdown";
import { BookOpen, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface DocEntry {
  slug: string;
  title: string;
  filename: string;
}

interface DocDetail {
  slug: string;
  title: string;
  content: string;
}

async function fetchDocs(): Promise<DocEntry[]> {
  const res = await fetch("/api/docs");
  if (!res.ok) throw new Error("Failed to load docs");
  return res.json();
}

async function fetchDoc(slug: string): Promise<DocDetail> {
  const res = await fetch(`/api/docs/${slug}`);
  if (!res.ok) throw new Error("Not found");
  return res.json();
}

function DocIndex({ docs, active }: { docs: DocEntry[]; active?: string }) {
  return (
    <nav className="space-y-1">
      {docs.map((doc) => (
        <Link
          key={doc.slug}
          to={`/docs/${doc.slug}`}
          className={cn(
            "flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors",
            active === doc.slug
              ? "bg-primary/10 text-primary font-medium"
              : "text-foreground hover:bg-muted",
          )}
        >
          <span className="truncate">{doc.title}</span>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        </Link>
      ))}
    </nav>
  );
}

export function DocsPage() {
  const { slug } = useParams<{ slug?: string }>();
  const [docs, setDocs] = useState<DocEntry[]>([]);
  const [detail, setDetail] = useState<DocDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDocs()
      .then(setDocs)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!slug) {
      setDetail(null);
      return;
    }
    setLoading(true);
    fetchDoc(slug)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading && docs.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-muted-foreground">Laden...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <BookOpen className="h-6 w-6 text-primary" />
          Dokumentation
        </h1>
        <p className="text-muted-foreground mt-1">
          Architektur, Anwendungsflow und technische Referenz
        </p>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Sidebar */}
        <div className="lg:w-64 shrink-0">
          <div className="bg-card rounded-xl border border-border shadow-sm p-4 lg:sticky lg:top-20">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
              Inhalte
            </h2>
            {docs.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Keine Dokumentation gefunden.
              </p>
            ) : (
              <DocIndex docs={docs} active={slug} />
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {loading ? (
            <div className="bg-card rounded-xl border border-border shadow-sm p-8 text-center text-muted-foreground animate-pulse">
              Laden...
            </div>
          ) : detail ? (
            <div className="bg-card rounded-xl border border-border shadow-sm p-6 sm:p-8">
              <article className="prose prose-sm max-w-none prose-headings:text-foreground prose-p:text-foreground/80 prose-strong:text-foreground prose-code:text-primary prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-pre:bg-[#1d1d1f] prose-pre:text-gray-300 prose-table:text-sm prose-th:text-left prose-th:font-semibold prose-th:border-b prose-th:border-border prose-th:pb-2 prose-td:border-b prose-td:border-border prose-td:py-2 prose-a:text-primary prose-li:text-foreground/80">
                <Markdown>{detail.content}</Markdown>
              </article>
            </div>
          ) : (
            <div className="bg-card rounded-xl border border-border shadow-sm p-8 text-center">
              <BookOpen className="h-12 w-12 text-muted-foreground/30 mx-auto mb-4" />
              <h2 className="text-lg font-medium mb-2">
                Willkommen zur DocFlow Dokumentation
              </h2>
              <p className="text-muted-foreground text-sm max-w-md mx-auto">
                Waehle einen Abschnitt aus der Seitenleiste, um die
                Dokumentation zu lesen.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
