export interface Run {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  photos_found: number;
  docs_processed: number;
  errors: number;
  log: string | null;
}

export interface Document {
  id: number;
  run_id: number;
  original_photo_id: string | null;
  original_filename: string;
  ocr_text: string;
  llm_provider: string;
  doc_type: string;
  tags: string;
  tags_list: string[];
  suggested_filename: string;
  saved_path: string | null;
  created_at: string;
  source: string;
  email_subject: string | null;
  email_sender: string | null;
  email_date: string | null;
  storage_backend: string | null;
  cloud_path: string | null;
}

export interface Settings {
  [key: string]: string;
}

const BASE = "/api";

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export async function getRuns(limit = 10): Promise<Run[]> {
  return fetchJSON(`${BASE}/runs?limit=${limit}`);
}

export async function getRun(id: number): Promise<Run> {
  return fetchJSON(`${BASE}/runs/${id}`);
}

export async function getDocuments(params: {
  q?: string;
  doc_type?: string;
  source?: string;
  run_id?: number;
  limit?: number;
  offset?: number;
}): Promise<Document[]> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.doc_type) sp.set("doc_type", params.doc_type);
  if (params.source) sp.set("source", params.source);
  if (params.run_id) sp.set("run_id", String(params.run_id));
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.offset) sp.set("offset", String(params.offset));
  return fetchJSON(`${BASE}/documents?${sp}`);
}

export async function getDocument(id: number): Promise<Document> {
  return fetchJSON(`${BASE}/documents/${id}`);
}

export async function getDocTypes(): Promise<string[]> {
  return fetchJSON(`${BASE}/doc-types`);
}

export async function getSettings(): Promise<Settings> {
  return fetchJSON(`${BASE}/settings`);
}

export async function saveSettings(data: Settings): Promise<void> {
  const res = await fetch(`${BASE}/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

export async function triggerRun(): Promise<void> {
  await fetch("/runs/trigger", { method: "POST" });
}
