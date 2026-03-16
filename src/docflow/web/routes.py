"""FastAPI route handlers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


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


# ── Dashboard ─────────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    db = _db(request)
    runs = db.list_runs(limit=10)
    return _templates(request).TemplateResponse(
        "index.html",
        {"request": request, "runs": runs},
    )


# ── Run detail ────────────────────────────────────────────────────────────────


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail(request: Request, run_id: int):
    db = _db(request)
    run = db.get_run(run_id)
    if not run:
        return HTMLResponse("Run not found", status_code=404)
    docs = db.list_documents(limit=200)
    docs = [d for d in docs if d.get("run_id") == run_id]
    docs = [_enrich(d) for d in docs]
    return _templates(request).TemplateResponse(
        "run_detail.html",
        {"request": request, "run": run, "docs": docs},
    )


# ── Documents ─────────────────────────────────────────────────────────────────


@router.get("/documents", response_class=HTMLResponse)
async def documents(
    request: Request,
    q: str | None = None,
    doc_type: str | None = None,
    tag: str | None = None,
    source: str | None = None,
    offset: int = 0,
    limit: int = 50,
):
    db = _db(request)

    if q:
        docs = db.search_documents(q, limit=limit)
    else:
        docs = db.list_documents(
            limit=limit,
            offset=offset,
            doc_type=doc_type or None,
            tag=tag or None,
            source=source or None,
        )

    docs = [_enrich(d) for d in docs]
    doc_types = db.list_doc_types()

    return _templates(request).TemplateResponse(
        "documents.html",
        {
            "request": request,
            "docs": docs,
            "doc_types": doc_types,
            "q": q or "",
            "selected_type": doc_type or "",
            "selected_tag": tag or "",
            "selected_source": source or "",
            "offset": offset,
            "limit": limit,
        },
    )


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


# ── Settings ──────────────────────────────────────────────────────────────────

# Fields exposed in the settings UI (secrets are excluded)
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


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, saved: bool = False):
    return _templates(request).TemplateResponse(
        "settings.html",
        {"request": request, "s": _settings(request), "saved": saved},
    )


@router.post("/settings")
async def settings_save(request: Request):
    form = await request.form()
    settings = _settings(request)

    updates: dict = {}
    for field in _SETTINGS_FIELDS:
        if field == "email_enabled":
            updates[field] = form.get("email_enabled") == "true"
        elif field in ("schedule_hour", "schedule_minute", "email_imap_port", "web_port"):
            raw = form.get(field, "")
            if raw != "":
                updates[field] = int(raw)
        elif field in ("output_dir", "icloud_docflow_path"):
            raw = form.get(field, "")
            if raw:
                updates[field] = Path(raw).expanduser().resolve()
        else:
            val = form.get(field, "")
            if val is not None:
                updates[field] = val

    new_settings = settings.model_copy(update=updates)
    request.app.state.settings = new_settings

    env_path = Path.cwd() / ".env"
    _write_env_file(new_settings, env_path)

    return RedirectResponse("/settings?saved=1", status_code=303)


# ── API: JSON endpoints ────────────────────────────────────────────────────────


@router.get("/api/runs")
async def api_runs(request: Request, limit: int = 10):
    return _db(request).list_runs(limit=limit)


@router.get("/api/runs/{run_id}")
async def api_run(request: Request, run_id: int):
    run = _db(request).get_run(run_id)
    if not run:
        return JSONResponse({"error": "not found"}, status_code=404)
    return run


@router.get("/api/documents")
async def api_documents(
    request: Request,
    q: str | None = None,
    doc_type: str | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    db = _db(request)
    if q:
        docs = db.search_documents(q, limit=limit)
    else:
        docs = db.list_documents(limit=limit, offset=offset, doc_type=doc_type, source=source)
    return [_enrich(d) for d in docs]


@router.get("/api/settings")
async def api_settings(request: Request):
    settings = _settings(request)
    return {field: str(getattr(settings, field)) for field in _SETTINGS_FIELDS}


@router.get("/api/documents/{doc_id}")
async def api_document(request: Request, doc_id: int):
    doc = _db(request).get_document(doc_id)
    if not doc:
        return JSONResponse({"error": "not found"}, status_code=404)
    return _enrich(doc)
