"""Application configuration via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Photos ────────────────────────────────────────────────────────────────
    photos_source: Literal["album", "all"] = "album"
    photos_album: str = "Dokumente"

    # ── Output ────────────────────────────────────────────────────────────────
    output_dir: Path = Path("~/Documents/DocFlow")
    db_path: Path = Path("~/Documents/DocFlow/docflow.db")

    # ── LLM ───────────────────────────────────────────────────────────────────
    llm_provider: Literal["anthropic", "ollama", "openrouter"] = "anthropic"
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-3-haiku"

    # ── Scheduler ─────────────────────────────────────────────────────────────
    schedule_hour: int = 2
    schedule_minute: int = 0

    # ── Web ───────────────────────────────────────────────────────────────────
    web_host: str = "127.0.0.1"
    web_port: int = 8765

    # ── Email ─────────────────────────────────────────────────────────────────
    email_enabled: bool = False
    email_imap_host: str = "imap.gmail.com"
    email_imap_port: int = 993
    email_username: str = ""
    email_password: str = ""
    email_folder: str = "INBOX"
    email_processed_folder: str = "DocFlow/Processed"
    email_filter_subject: str = ""  # Optional subject substring filter

    # ── Storage ───────────────────────────────────────────────────────────────
    storage_backend: Literal["local", "icloud", "s3"] = "local"
    icloud_docflow_path: Path = Path("~/Library/Mobile Documents/com~apple~CloudDocs/DocFlow")
    s3_bucket: str = ""
    s3_prefix: str = "docflow/"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_endpoint_url: str = ""  # For S3-compatible services (Backblaze, MinIO, etc.)

    @field_validator("output_dir", "db_path", "icloud_docflow_path", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        return Path(str(v)).expanduser().resolve()

    def ensure_dirs(self) -> None:
        """Create output directories if they don't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
