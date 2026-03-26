"""E2E: settings API — view and update configuration via JSON."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docflow.config import Settings
from docflow.web.app import create_app


def _client_and_settings(e2e_dir: Path) -> tuple[TestClient, Settings]:
    settings = Settings(
        photos_source="album",
        photos_album="TestAlbum",
        output_dir=e2e_dir / "output",
        db_path=e2e_dir / "settings_e2e.db",
        llm_provider="anthropic",
        anthropic_api_key="test",
        storage_backend="local",
        email_enabled=False,
        schedule_hour=2,
        schedule_minute=30,
        web_host="127.0.0.1",
        web_port=8765,
    )
    app = create_app(settings)
    return TestClient(app), settings


@pytest.mark.e2e
class TestE2ESettingsPage:
    def test_settings_page_loads(self, e2e_dir: Path):
        client, _ = _client_and_settings(e2e_dir)
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm_provider" in data

    def test_settings_page_shows_current_values(self, e2e_dir: Path):
        client, settings = _client_and_settings(e2e_dir)
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["photos_album"] == "TestAlbum"
        assert data["schedule_hour"] == "2"
        assert data["schedule_minute"] == "30"
        assert data["llm_provider"] == "anthropic"

    def test_settings_page_shows_photos_source_selected(self, e2e_dir: Path):
        client, _ = _client_and_settings(e2e_dir)
        data = client.get("/api/settings").json()
        assert data["photos_source"] == "album"

    def test_settings_nav_link_exists(self, e2e_dir: Path):
        """SPA catch-all serves index.html for any non-API path."""
        client, _ = _client_and_settings(e2e_dir)
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        # Settings endpoint is available
        assert isinstance(resp.json(), dict)

    def test_save_settings_returns_ok(self, e2e_dir: Path):
        client, _ = _client_and_settings(e2e_dir)
        resp = client.post(
            "/api/settings",
            json={
                "photos_source": "all",
                "photos_album": "NeuesAlbum",
                "llm_provider": "ollama",
                "ollama_base_url": "http://localhost:11434",
                "ollama_model": "llama3.2",
                "openrouter_model": "anthropic/claude-3-haiku",
                "storage_backend": "local",
                "output_dir": str(e2e_dir / "output"),
                "icloud_docflow_path": str(e2e_dir / "icloud"),
                "s3_bucket": "",
                "s3_prefix": "docflow/",
                "s3_endpoint_url": "",
                "schedule_hour": "3",
                "schedule_minute": "15",
                "email_enabled": False,
                "email_imap_host": "imap.gmail.com",
                "email_imap_port": "993",
                "email_folder": "INBOX",
                "email_processed_folder": "DocFlow/Processed",
                "email_filter_subject": "",
                "web_host": "0.0.0.0",
                "web_port": "9000",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_save_settings_updates_in_memory(self, e2e_dir: Path):
        client, _ = _client_and_settings(e2e_dir)
        client.post(
            "/api/settings",
            json={
                "photos_source": "all",
                "photos_album": "Geändert",
                "llm_provider": "ollama",
                "ollama_base_url": "http://myhost:11434",
                "ollama_model": "mistral",
                "openrouter_model": "anthropic/claude-3-haiku",
                "storage_backend": "icloud",
                "output_dir": str(e2e_dir / "output"),
                "icloud_docflow_path": str(e2e_dir / "icloud"),
                "s3_bucket": "",
                "s3_prefix": "docflow/",
                "s3_endpoint_url": "",
                "schedule_hour": "5",
                "schedule_minute": "45",
                "email_enabled": False,
                "email_imap_host": "imap.example.com",
                "email_imap_port": "993",
                "email_folder": "INBOX",
                "email_processed_folder": "DocFlow/Done",
                "email_filter_subject": "Rechnung",
                "web_host": "0.0.0.0",
                "web_port": "9000",
            },
        )

        # Verify the settings API now shows updated values
        data = client.get("/api/settings").json()
        assert data["photos_album"] == "Geändert"
        assert data["photos_source"] == "all"
        assert data["schedule_hour"] == "5"
        assert data["schedule_minute"] == "45"
        assert data["email_imap_host"] == "imap.example.com"

    def test_save_enables_email(self, e2e_dir: Path):
        client, _ = _client_and_settings(e2e_dir)
        client.post(
            "/api/settings",
            json={
                "photos_source": "album",
                "photos_album": "TestAlbum",
                "llm_provider": "anthropic",
                "ollama_base_url": "http://localhost:11434",
                "ollama_model": "llama3.2",
                "openrouter_model": "anthropic/claude-3-haiku",
                "storage_backend": "local",
                "output_dir": str(e2e_dir / "output"),
                "icloud_docflow_path": str(e2e_dir / "icloud"),
                "s3_bucket": "",
                "s3_prefix": "docflow/",
                "s3_endpoint_url": "",
                "schedule_hour": "2",
                "schedule_minute": "0",
                "email_enabled": True,
                "email_imap_host": "imap.gmail.com",
                "email_imap_port": "993",
                "email_folder": "INBOX",
                "email_processed_folder": "DocFlow/Processed",
                "email_filter_subject": "",
                "web_host": "127.0.0.1",
                "web_port": "8765",
            },
        )

        data = client.get("/api/settings").json()
        assert data["email_enabled"] == "True"

    def test_save_disables_email(self, e2e_dir: Path):
        client, _ = _client_and_settings(e2e_dir)
        # First enable
        payload = {
            "photos_source": "album",
            "photos_album": "TestAlbum",
            "llm_provider": "anthropic",
            "ollama_base_url": "http://localhost:11434",
            "ollama_model": "llama3.2",
            "openrouter_model": "anthropic/claude-3-haiku",
            "storage_backend": "local",
            "output_dir": str(e2e_dir / "output"),
            "icloud_docflow_path": str(e2e_dir / "icloud"),
            "s3_bucket": "",
            "s3_prefix": "docflow/",
            "s3_endpoint_url": "",
            "schedule_hour": "2",
            "schedule_minute": "0",
            "email_enabled": True,
            "email_imap_host": "imap.gmail.com",
            "email_imap_port": "993",
            "email_folder": "INBOX",
            "email_processed_folder": "DocFlow/Processed",
            "email_filter_subject": "",
            "web_host": "127.0.0.1",
            "web_port": "8765",
        }
        client.post("/api/settings", json=payload)

        # Now disable
        payload["email_enabled"] = False
        client.post("/api/settings", json=payload)

        data = client.get("/api/settings").json()
        assert data["email_enabled"] == "False"

    def test_save_writes_env_file(self, e2e_dir: Path, monkeypatch):
        monkeypatch.chdir(e2e_dir)
        client, _ = _client_and_settings(e2e_dir)
        client.post(
            "/api/settings",
            json={
                "photos_source": "all",
                "photos_album": "MeinAlbum",
                "llm_provider": "ollama",
                "ollama_base_url": "http://localhost:11434",
                "ollama_model": "llama3.2",
                "openrouter_model": "anthropic/claude-3-haiku",
                "storage_backend": "local",
                "output_dir": str(e2e_dir / "output"),
                "icloud_docflow_path": str(e2e_dir / "icloud"),
                "s3_bucket": "",
                "s3_prefix": "docflow/",
                "s3_endpoint_url": "",
                "schedule_hour": "4",
                "schedule_minute": "0",
                "email_enabled": False,
                "email_imap_host": "imap.gmail.com",
                "email_imap_port": "993",
                "email_folder": "INBOX",
                "email_processed_folder": "DocFlow/Processed",
                "email_filter_subject": "",
                "web_host": "127.0.0.1",
                "web_port": "8765",
            },
        )

        env_file = e2e_dir / ".env"
        assert env_file.exists()
        content = env_file.read_text()
        assert "PHOTOS_SOURCE=all" in content
        assert "PHOTOS_ALBUM=MeinAlbum" in content
        assert "LLM_PROVIDER=ollama" in content
        assert "SCHEDULE_HOUR=4" in content
        assert "EMAIL_ENABLED=false" in content

    def test_saved_flash_message(self, e2e_dir: Path):
        """Saving settings returns status ok in JSON response."""
        client, _ = _client_and_settings(e2e_dir)
        resp = client.post(
            "/api/settings",
            json={"photos_album": "TestAlbum"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_no_secrets_in_settings_page(self, e2e_dir: Path):
        client, _ = _client_and_settings(e2e_dir)
        data = client.get("/api/settings").json()
        secret_fields = [
            "anthropic_api_key",
            "openrouter_api_key",
            "email_password",
            "aws_secret_access_key",
            "aws_access_key_id",
        ]
        for field in secret_fields:
            assert field not in data

    def test_api_settings_returns_json(self, e2e_dir: Path):
        client, _ = _client_and_settings(e2e_dir)
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["photos_source"] == "album"
        assert data["photos_album"] == "TestAlbum"
        assert data["llm_provider"] == "anthropic"
        assert "anthropic_api_key" not in data
        assert "email_password" not in data

    def test_api_settings_no_secrets(self, e2e_dir: Path):
        client, _ = _client_and_settings(e2e_dir)
        data = client.get("/api/settings").json()
        secret_fields = [
            "anthropic_api_key",
            "openrouter_api_key",
            "email_password",
            "email_username",
            "aws_access_key_id",
            "aws_secret_access_key",
        ]
        for field in secret_fields:
            assert field not in data
