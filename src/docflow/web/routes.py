"""FastAPI route handlers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

router = APIRouter()


def _db(request: Request):
    return request.app.state.db


def _settings(request: Request):
    return request.app.state.settings


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_tags(doc: dict) -> list[str]:
    raw = doc.get("tags") or "[]"
    try:
        return json.loads(raw)
    except Exception:
        return []


def _enrich(doc: dict) -> dict:
    doc = dict(doc)
    doc["tags_list"] = _parse_tags(doc)
    return doc


# ── Trigger manual run ────────────────────────────────────────────────────────


def _do_run(settings, db_path):
    """Run pipeline in a background thread (called from BackgroundTasks)."""
    from docflow.db import Database
    from docflow.pipeline import Pipeline

    db = Database(db_path)
    pipeline = Pipeline(settings=settings, db=db)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(pipeline.run())
    finally:
        loop.close()


@router.post("/runs/trigger")
async def trigger_run(request: Request, background_tasks: BackgroundTasks):
    settings = _settings(request)
    background_tasks.add_task(_do_run, settings, settings.db_path)
    return RedirectResponse("/", status_code=303)


# ── Settings fields ────────────────────────────────────────────────────────────

_SETTINGS_FIELDS: list[str] = [
    "photos_source",
    "photos_album",
    "llm_provider",
    "ollama_base_url",
    "ollama_model",
    "openrouter_model",
    "storage_backend",
    "output_dir",
    "icloud_docflow_path",
    "s3_bucket",
    "s3_prefix",
    "s3_endpoint_url",
    "schedule_hour",
    "schedule_minute",
    "email_enabled",
    "email_imap_host",
    "email_imap_port",
    "email_folder",
    "email_processed_folder",
    "email_filter_subject",
    "web_host",
    "web_port",
]


def _write_env_file(settings, env_path: Path) -> None:
    """Write non-secret settings to a .env file."""
    lines: list[str] = []
    for field in _SETTINGS_FIELDS:
        val = getattr(settings, field)
        if isinstance(val, bool):
            lines.append(f"{field.upper()}={'true' if val else 'false'}")
        elif isinstance(val, Path):
            lines.append(f"{field.upper()}={val}")
        else:
            lines.append(f"{field.upper()}={val}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── API: Runs ─────────────────────────────────────────────────────────────────


@router.get("/api/runs")
async def api_runs(request: Request, limit: int = 10):
    return _db(request).list_runs(limit=limit)


@router.get("/api/runs/{run_id}")
async def api_run(request: Request, run_id: int):
    run = _db(request).get_run(run_id)
    if not run:
        return JSONResponse({"error": "not found"}, status_code=404)
    return run


# ── API: Documents ────────────────────────────────────────────────────────────


@router.get("/api/documents")
async def api_documents(
    request: Request,
    q: str | None = None,
    doc_type: str | None = None,
    source: str | None = None,
    run_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
):
    db = _db(request)
    if q:
        docs = db.search_documents(q, limit=limit)
    else:
        docs = db.list_documents(limit=limit, offset=offset, doc_type=doc_type, source=source)
    if run_id is not None:
        docs = [d for d in docs if d.get("run_id") == run_id]
    return [_enrich(d) for d in docs]


@router.get("/api/doc-types")
async def api_doc_types(request: Request):
    return _db(request).list_doc_types()


@router.get("/api/documents/{doc_id}")
async def api_document(request: Request, doc_id: int):
    doc = _db(request).get_document(doc_id)
    if not doc:
        return JSONResponse({"error": "not found"}, status_code=404)
    return _enrich(doc)


@router.get("/api/documents/{doc_id}/file")
async def api_document_file(request: Request, doc_id: int):
    """Serve the stored PDF file for a document."""
    doc = _db(request).get_document(doc_id)
    if not doc:
        return JSONResponse({"error": "not found"}, status_code=404)
    file_path = Path(doc.get("saved_path") or "")
    if not file_path.is_file():
        return JSONResponse({"error": "file not found"}, status_code=404)
    return FileResponse(
        file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


# ── API: Settings ─────────────────────────────────────────────────────────────


@router.get("/api/settings")
async def api_settings(request: Request):
    settings = _settings(request)
    return {field: str(getattr(settings, field)) for field in _SETTINGS_FIELDS}


@router.post("/api/settings")
async def api_settings_save(request: Request):
    data = await request.json()
    settings = _settings(request)

    updates: dict = {}
    for field in _SETTINGS_FIELDS:
        if field not in data:
            continue
        val = data[field]
        if field == "email_enabled":
            updates[field] = val in (True, "true", "True")
        elif field in ("schedule_hour", "schedule_minute", "email_imap_port", "web_port"):
            updates[field] = int(val)
        elif field in ("output_dir", "icloud_docflow_path"):
            if val:
                updates[field] = Path(val).expanduser().resolve()
        else:
            updates[field] = val

    new_settings = settings.model_copy(update=updates)
    request.app.state.settings = new_settings

    env_path = Path.cwd() / ".env"
    _write_env_file(new_settings, env_path)

    return {"status": "ok"}


# ── API: Ollama ───────────────────────────────────────────────────────────────


@router.get("/api/ollama/models")
async def api_ollama_models(request: Request):
    """Fetch available models from the configured Ollama instance."""
    import httpx

    settings = _settings(request)
    base_url = str(getattr(settings, "ollama_base_url", "http://localhost:11434"))
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


# ── API: Documentation ────────────────────────────────────────────────────────

_DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs"


@router.get("/api/docs")
async def api_docs_list():
    """List available documentation files."""
    if not _DOCS_DIR.is_dir():
        return []
    return [
        {"slug": p.stem, "title": _extract_title(p), "filename": p.name}
        for p in sorted(_DOCS_DIR.glob("*.md"))
    ]


@router.get("/api/docs/{slug}")
async def api_docs_detail(slug: str):
    """Return the markdown content of a documentation file."""
    md_path = _DOCS_DIR / f"{slug}.md"
    if not md_path.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    content = md_path.read_text(encoding="utf-8")
    return {"slug": slug, "title": _extract_title(md_path), "content": content}


def _extract_title(path: Path) -> str:
    """Extract the first H1 heading from a markdown file, or use the filename."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except Exception:
        pass
    return path.stem.replace("_", " ").replace("-", " ").title()
