import { useEffect, useState } from "react";
import { getSettings, saveSettings, type Settings } from "@/lib/api";
import { Save, CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

const LLM_PROVIDERS = [
  { value: "anthropic", label: "Anthropic Claude" },
  { value: "ollama", label: "Ollama (lokal)" },
  { value: "openrouter", label: "OpenRouter" },
] as const;

const STORAGE_BACKENDS = [
  { value: "local", label: "Lokal" },
  { value: "icloud", label: "iCloud Drive" },
  { value: "s3", label: "S3 / Cloud" },
] as const;

const ANTHROPIC_MODELS = [
  "claude-sonnet-4-6",
  "claude-opus-4-6",
  "claude-haiku-4-5-20251001",
  "claude-sonnet-4-5-20250514",
];

const OPENROUTER_MODELS = [
  "anthropic/claude-sonnet-4-5",
  "anthropic/claude-3.5-haiku",
  "google/gemini-2.0-flash-001",
  "meta-llama/llama-3.3-70b-instruct",
  "mistralai/mistral-small-3.1-24b-instruct",
];

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
        </h3>
        {description && (
          <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
        )}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">{children}</div>
    </div>
  );
}

function Field({
  label,
  name,
  value,
  onChange,
  type = "text",
  options,
  placeholder,
  hint,
  span2,
}: {
  label: string;
  name: string;
  value: string;
  onChange: (name: string, value: string) => void;
  type?: "text" | "number" | "select" | "checkbox";
  options?: { value: string; label: string }[];
  placeholder?: string;
  hint?: string;
  span2?: boolean;
}) {
  const wrapperClass = span2 ? "sm:col-span-2" : "";

  if (type === "select" && options) {
    return (
      <div className={wrapperClass}>
        <label className="block text-sm font-medium mb-1.5">{label}</label>
        <select
          value={value}
          onChange={(e) => onChange(name, e.target.value)}
          className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {hint && <p className="text-xs text-muted-foreground mt-1">{hint}</p>}
      </div>
    );
  }

  if (type === "checkbox") {
    return (
      <div className={cn("flex items-center gap-3", wrapperClass)}>
        <input
          type="checkbox"
          id={name}
          checked={value === "true" || value === "True"}
          onChange={(e) => onChange(name, e.target.checked ? "true" : "false")}
          className="h-4 w-4 rounded border-input accent-primary"
        />
        <label htmlFor={name} className="text-sm font-medium cursor-pointer">
          {label}
        </label>
        {hint && (
          <span className="text-xs text-muted-foreground">({hint})</span>
        )}
      </div>
    );
  }

  return (
    <div className={wrapperClass}>
      <label className="block text-sm font-medium mb-1.5">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(name, e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />
      {hint && <p className="text-xs text-muted-foreground mt-1">{hint}</p>}
    </div>
  );
}

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  useEffect(() => {
    getSettings()
      .then(setSettings)
      .finally(() => setLoading(false));
  }, []);

  const provider = settings.llm_provider ?? "anthropic";
  const backend = settings.storage_backend ?? "local";

  // Fetch Ollama models when provider is ollama
  useEffect(() => {
    if (provider === "ollama") {
      fetchOllamaModels();
    }
  }, [provider]);

  const fetchOllamaModels = async () => {
    setLoadingModels(true);
    try {
      const res = await fetch("/api/ollama/models");
      const models: string[] = await res.json();
      setOllamaModels(models);
    } catch {
      setOllamaModels([]);
    } finally {
      setLoadingModels(false);
    }
  };

  const handleChange = (name: string, value: string) => {
    setSettings((prev) => ({ ...prev, [name]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveSettings(settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } finally {
      setSaving(false);
    }
  };

  const v = (key: string) => settings[key] ?? "";

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-muted-foreground">Laden...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Einstellungen
          </h1>
          <p className="text-muted-foreground mt-1">
            Konfiguriere DocFlow Parameter
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className={cn(
            "flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all",
            saved
              ? "bg-success/10 text-success border border-success/20"
              : "bg-primary text-primary-foreground hover:bg-primary/90 active:scale-95 disabled:opacity-50",
          )}
        >
          {saved ? (
            <>
              <CheckCircle2 className="h-4 w-4" />
              Gespeichert
            </>
          ) : saving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Speichern...
            </>
          ) : (
            <>
              <Save className="h-4 w-4" />
              Speichern
            </>
          )}
        </button>
      </div>

      {saved && (
        <div className="bg-success/10 text-success border border-success/20 rounded-lg px-4 py-3 text-sm font-medium flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4" />
          Einstellungen erfolgreich gespeichert.
        </div>
      )}

      <div className="space-y-6">
        {/* ── Photos ───────────────────────────────────────── */}
        <div className="bg-card rounded-xl border border-border shadow-sm p-6 space-y-6">
          <Section title="Photos" description="Quelle fuer Dokument-Fotos">
            <Field
              label="Quelle"
              name="photos_source"
              value={v("photos_source")}
              onChange={handleChange}
              type="select"
              options={[
                { value: "album", label: "Bestimmtes Album" },
                { value: "all", label: "Gesamte Mediathek" },
              ]}
            />
            <Field
              label="Album-Name"
              name="photos_album"
              value={v("photos_album")}
              onChange={handleChange}
              placeholder="z.B. Dokumente"
              hint="Name des Albums in Apple Photos"
            />
          </Section>
        </div>

        {/* ── LLM ─────────────────────────────────────────── */}
        <div className="bg-card rounded-xl border border-border shadow-sm p-6 space-y-6">
          <Section
            title="KI-Modell"
            description="Anbieter und Modell fuer die Dokumentenklassifikation"
          >
            <Field
              label="Anbieter"
              name="llm_provider"
              value={provider}
              onChange={handleChange}
              type="select"
              options={LLM_PROVIDERS.map((p) => ({
                value: p.value,
                label: p.label,
              }))}
              span2
            />

            {/* Anthropic-spezifisch */}
            {provider === "anthropic" && (
              <Field
                label="Modell"
                name="anthropic_model"
                value={v("anthropic_model") || ANTHROPIC_MODELS[0]}
                onChange={handleChange}
                type="select"
                options={ANTHROPIC_MODELS.map((m) => ({
                  value: m,
                  label: m,
                }))}
                hint="Benoetigt ANTHROPIC_API_KEY in .env"
              />
            )}

            {/* Ollama-spezifisch */}
            {provider === "ollama" && (
              <>
                <Field
                  label="Ollama URL"
                  name="ollama_base_url"
                  value={v("ollama_base_url") || "http://localhost:11434"}
                  onChange={handleChange}
                  placeholder="http://localhost:11434"
                />
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-sm font-medium">Modell</label>
                    <button
                      onClick={fetchOllamaModels}
                      disabled={loadingModels}
                      className="text-xs text-primary hover:text-primary/80 flex items-center gap-1"
                    >
                      <RefreshCw
                        className={cn(
                          "h-3 w-3",
                          loadingModels && "animate-spin",
                        )}
                      />
                      Modelle laden
                    </button>
                  </div>
                  {ollamaModels.length > 0 ? (
                    <select
                      value={v("ollama_model") || ollamaModels[0]}
                      onChange={(e) =>
                        handleChange("ollama_model", e.target.value)
                      }
                      className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      {ollamaModels.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={v("ollama_model") || "llama3.2"}
                      onChange={(e) =>
                        handleChange("ollama_model", e.target.value)
                      }
                      placeholder="llama3.2"
                      className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  )}
                  {loadingModels && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Lade Modelle von Ollama...
                    </p>
                  )}
                  {!loadingModels && ollamaModels.length === 0 && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Keine Modelle gefunden. Ist Ollama gestartet?
                    </p>
                  )}
                </div>
              </>
            )}

            {/* OpenRouter-spezifisch */}
            {provider === "openrouter" && (
              <Field
                label="Modell"
                name="openrouter_model"
                value={v("openrouter_model") || OPENROUTER_MODELS[0]}
                onChange={handleChange}
                type="select"
                options={OPENROUTER_MODELS.map((m) => ({
                  value: m,
                  label: m,
                }))}
                hint="Benoetigt OPENROUTER_API_KEY in .env"
              />
            )}
          </Section>
        </div>

        {/* ── Storage ─────────────────────────────────────── */}
        <div className="bg-card rounded-xl border border-border shadow-sm p-6 space-y-6">
          <Section
            title="Speicher"
            description="Wo verarbeitete PDFs abgelegt werden"
          >
            <Field
              label="Backend"
              name="storage_backend"
              value={backend}
              onChange={handleChange}
              type="select"
              options={STORAGE_BACKENDS.map((b) => ({
                value: b.value,
                label: b.label,
              }))}
              span2
            />

            {backend === "local" && (
              <Field
                label="Ausgabeverzeichnis"
                name="output_dir"
                value={v("output_dir")}
                onChange={handleChange}
                placeholder="~/Documents/DocFlow/output"
                hint="Absoluter Pfad zum Ausgabeordner"
                span2
              />
            )}

            {backend === "icloud" && (
              <Field
                label="iCloud-Pfad"
                name="icloud_docflow_path"
                value={v("icloud_docflow_path")}
                onChange={handleChange}
                placeholder="~/Library/Mobile Documents/.../DocFlow"
                hint="Pfad im iCloud Drive Container"
                span2
              />
            )}

            {backend === "s3" && (
              <>
                <Field
                  label="S3 Bucket"
                  name="s3_bucket"
                  value={v("s3_bucket")}
                  onChange={handleChange}
                  placeholder="mein-docflow-bucket"
                />
                <Field
                  label="S3 Prefix"
                  name="s3_prefix"
                  value={v("s3_prefix") || "docflow/"}
                  onChange={handleChange}
                  placeholder="docflow/"
                />
                <Field
                  label="Endpoint URL"
                  name="s3_endpoint_url"
                  value={v("s3_endpoint_url")}
                  onChange={handleChange}
                  placeholder="https://s3.eu-central-1.amazonaws.com"
                  hint="Leer fuer AWS, oder URL fuer B2/MinIO/R2"
                  span2
                />
              </>
            )}
          </Section>
        </div>

        {/* ── Schedule ────────────────────────────────────── */}
        <div className="bg-card rounded-xl border border-border shadow-sm p-6">
          <Section
            title="Zeitplan"
            description="Taeglicher automatischer Pipeline-Lauf"
          >
            <Field
              label="Stunde (UTC)"
              name="schedule_hour"
              value={v("schedule_hour")}
              onChange={handleChange}
              type="number"
              hint="0-23, Uhrzeit in UTC"
            />
            <Field
              label="Minute"
              name="schedule_minute"
              value={v("schedule_minute")}
              onChange={handleChange}
              type="number"
              hint="0-59"
            />
          </Section>
        </div>

        {/* ── Email ───────────────────────────────────────── */}
        <div className="bg-card rounded-xl border border-border shadow-sm p-6 space-y-6">
          <Section
            title="E-Mail-Eingang"
            description="Dokumente aus E-Mail-Anhaengen verarbeiten"
          >
            <Field
              label="E-Mail-Eingang aktivieren"
              name="email_enabled"
              value={v("email_enabled")}
              onChange={handleChange}
              type="checkbox"
              span2
            />

            {(v("email_enabled") === "true" ||
              v("email_enabled") === "True") && (
              <>
                <Field
                  label="IMAP-Host"
                  name="email_imap_host"
                  value={v("email_imap_host") || "imap.gmail.com"}
                  onChange={handleChange}
                  placeholder="imap.gmail.com"
                />
                <Field
                  label="IMAP-Port"
                  name="email_imap_port"
                  value={v("email_imap_port") || "993"}
                  onChange={handleChange}
                  type="number"
                  hint="993 fuer SSL"
                />
                <Field
                  label="Ordner"
                  name="email_folder"
                  value={v("email_folder") || "INBOX"}
                  onChange={handleChange}
                  placeholder="INBOX"
                />
                <Field
                  label="Verarbeitet-Ordner"
                  name="email_processed_folder"
                  value={
                    v("email_processed_folder") || "DocFlow/Processed"
                  }
                  onChange={handleChange}
                  placeholder="DocFlow/Processed"
                />
                <Field
                  label="Betreff-Filter"
                  name="email_filter_subject"
                  value={v("email_filter_subject")}
                  onChange={handleChange}
                  placeholder="Rechnung"
                  hint="Optional: nur Nachrichten mit diesem Betreff"
                  span2
                />
              </>
            )}
          </Section>
        </div>

        {/* ── Web Server ──────────────────────────────────── */}
        <div className="bg-card rounded-xl border border-border shadow-sm p-6">
          <Section title="Webserver" description="Host und Port der Web-UI">
            <Field
              label="Host"
              name="web_host"
              value={v("web_host")}
              onChange={handleChange}
              hint="0.0.0.0 fuer externen Zugriff"
            />
            <Field
              label="Port"
              name="web_port"
              value={v("web_port")}
              onChange={handleChange}
              type="number"
            />
          </Section>
        </div>
      </div>
    </div>
  );
}
