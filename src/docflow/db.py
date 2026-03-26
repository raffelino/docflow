"""SQLite database with FTS5 full-text search."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    status TEXT DEFAULT 'running',
    photos_found INTEGER DEFAULT 0,
    docs_processed INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    log TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER REFERENCES runs(id),
    original_photo_id TEXT,
    original_filename TEXT,
    ocr_text TEXT,
    llm_provider TEXT,
    doc_type TEXT,
    tags TEXT,
    suggested_filename TEXT,
    saved_path TEXT,
    created_at TIMESTAMP,
    -- Source tracking
    source TEXT DEFAULT 'photos',
    email_subject TEXT,
    email_sender TEXT,
    email_date TIMESTAMP,
    -- Storage
    storage_backend TEXT,
    cloud_path TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    ocr_text,
    doc_type,
    tags,
    suggested_filename,
    content=documents,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, ocr_text, doc_type, tags, suggested_filename)
    VALUES (new.id, new.ocr_text, new.doc_type, new.tags, new.suggested_filename);
END;

CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, ocr_text, doc_type, tags, suggested_filename)
    VALUES ('delete', old.id, old.ocr_text, old.doc_type, old.tags, old.suggested_filename);
END;

CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, ocr_text, doc_type, tags, suggested_filename)
    VALUES ('delete', old.id, old.ocr_text, old.doc_type, old.tags, old.suggested_filename);
    INSERT INTO documents_fts(rowid, ocr_text, doc_type, tags, suggested_filename)
    VALUES (new.id, new.ocr_text, new.doc_type, new.tags, new.suggested_filename);
END;
"""

# Migration: add new columns to existing databases
MIGRATIONS = [
    "ALTER TABLE documents ADD COLUMN source TEXT DEFAULT 'photos'",
    "ALTER TABLE documents ADD COLUMN email_subject TEXT",
    "ALTER TABLE documents ADD COLUMN email_sender TEXT",
    "ALTER TABLE documents ADD COLUMN email_date TIMESTAMP",
    "ALTER TABLE documents ADD COLUMN storage_backend TEXT",
    "ALTER TABLE documents ADD COLUMN cloud_path TEXT",
    "ALTER TABLE documents ADD COLUMN file_hash TEXT",
]


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Idempotently apply schema migrations (ADD COLUMN is safe to retry)."""
    for sql in MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError as e:
            # "duplicate column name" means migration already applied — safe to ignore
            if "duplicate column" not in str(e).lower():
                raise


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            _apply_migrations(conn)
        logger.info("Database initialized", path=str(self.db_path))

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Runs ──────────────────────────────────────────────────────────────────

    def create_run(self) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO runs (started_at, status) VALUES (?, 'running')",
                (datetime.utcnow(),),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def finish_run(
        self,
        run_id: int,
        status: str,
        photos_found: int,
        docs_processed: int,
        errors: int,
        log: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE runs
                   SET finished_at=?, status=?, photos_found=?,
                       docs_processed=?, errors=?, log=?
                   WHERE id=?""",
                (datetime.utcnow(), status, photos_found, docs_processed, errors, log, run_id),
            )

    def get_run(self, run_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            return dict(row) if row else None

    def list_runs(self, limit: int = 10) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Documents ─────────────────────────────────────────────────────────────

    def insert_document(
        self,
        run_id: int,
        original_photo_id: str,
        original_filename: str,
        ocr_text: str,
        llm_provider: str,
        doc_type: str,
        tags: list[str],
        suggested_filename: str,
        saved_path: str,
        source: str = "photos",
        email_subject: str | None = None,
        email_sender: str | None = None,
        email_date: datetime | None = None,
        storage_backend: str | None = None,
        cloud_path: str | None = None,
        file_hash: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO documents
                   (run_id, original_photo_id, original_filename, ocr_text,
                    llm_provider, doc_type, tags, suggested_filename, saved_path, created_at,
                    source, email_subject, email_sender, email_date,
                    storage_backend, cloud_path, file_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    original_photo_id,
                    original_filename,
                    ocr_text,
                    llm_provider,
                    doc_type,
                    json.dumps(tags, ensure_ascii=False),
                    suggested_filename,
                    saved_path,
                    datetime.utcnow(),
                    source,
                    email_subject,
                    email_sender,
                    email_date,
                    storage_backend,
                    cloud_path,
                    file_hash,
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def list_documents(
        self,
        limit: int = 50,
        offset: int = 0,
        doc_type: str | None = None,
        tag: str | None = None,
        source: str | None = None,
    ) -> list[dict]:
        with self._connect() as conn:
            clauses: list[str] = []
            params: list = []
            if doc_type:
                clauses.append("doc_type = ?")
                params.append(doc_type)
            if tag:
                clauses.append("tags LIKE ?")
                params.append(f'%"{tag}"%')
            if source:
                clauses.append("source = ?")
                params.append(source)
            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = conn.execute(
                f"SELECT * FROM documents {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            return [dict(r) for r in rows]

    def search_documents(self, query: str, limit: int = 50) -> list[dict]:
        """Full-text search via FTS5."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT d.*
                   FROM documents d
                   JOIN documents_fts fts ON fts.rowid = d.id
                   WHERE documents_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_document(self, doc_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
            return dict(row) if row else None

    def document_exists(self, photo_id: str | None = None, file_hash: str | None = None) -> bool:
        """Check if a document with the given photo UUID or file hash already exists."""
        with self._connect() as conn:
            if photo_id:
                row = conn.execute(
                    "SELECT 1 FROM documents WHERE original_photo_id = ? LIMIT 1",
                    (photo_id,),
                ).fetchone()
                if row:
                    return True
            if file_hash:
                row = conn.execute(
                    "SELECT 1 FROM documents WHERE file_hash = ? LIMIT 1",
                    (file_hash,),
                ).fetchone()
                if row:
                    return True
        return False

    def list_doc_types(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT doc_type FROM documents WHERE doc_type IS NOT NULL ORDER BY doc_type"
            ).fetchall()
            return [r[0] for r in rows]
