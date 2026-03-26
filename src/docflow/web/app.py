"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from docflow.config import Settings
from docflow.db import Database
from docflow.web.routes import router

STATIC_DIR = Path(__file__).parent / "static"
DOCS_DIR = Path(__file__).parent / "docs-static"


def create_app(settings: Settings) -> FastAPI:
    settings.ensure_dirs()
    db = Database(settings.db_path)

    app = FastAPI(title="DocFlow", version="0.1.0")

    app.state.settings = settings
    app.state.db = db

    # VitePress documentation site at /docs/
    has_docs = DOCS_DIR.is_dir() and (DOCS_DIR / "index.html").exists()

    if has_docs:
        if (DOCS_DIR / "assets").is_dir():
            app.mount(
                "/docs/assets",
                StaticFiles(directory=str(DOCS_DIR / "assets")),
                name="docs-assets",
            )

        @app.get("/docs", response_class=HTMLResponse)
        @app.get("/docs/", response_class=HTMLResponse)
        async def docs_index() -> FileResponse:
            return FileResponse(DOCS_DIR / "index.html")

        @app.get("/docs/{path:path}", response_class=HTMLResponse)
        async def docs_pages(path: str) -> FileResponse:
            file_path = DOCS_DIR / path
            if file_path.is_file():
                return FileResponse(file_path)
            html_path = DOCS_DIR / f"{path}.html"
            if html_path.is_file():
                return FileResponse(html_path)
            index_path = DOCS_DIR / path / "index.html"
            if index_path.is_file():
                return FileResponse(index_path)
            return FileResponse(DOCS_DIR / "index.html")

    # React SPA static assets
    if (STATIC_DIR / "assets").is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(STATIC_DIR / "assets")),
            name="assets",
        )

    # Include API + trigger routes
    app.include_router(router, prefix="")

    # SPA catch-all: serve index.html for all non-API routes
    @app.get("/{path:path}", response_class=HTMLResponse)
    async def spa_fallback(path: str) -> FileResponse:
        file_path = STATIC_DIR / path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")

    return app
