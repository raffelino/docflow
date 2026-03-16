"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from docflow.config import Settings
from docflow.db import Database
from docflow.web.routes import router

TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app(settings: Settings) -> FastAPI:
    settings.ensure_dirs()
    db = Database(settings.db_path)

    app = FastAPI(title="DocFlow", version="0.1.0")

    # Attach shared objects via app.state
    app.state.settings = settings
    app.state.db = db
    app.state.templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    app.include_router(router)

    return app
