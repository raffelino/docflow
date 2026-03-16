"""E2E: scheduler triggers a run and DB records it."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docflow.config import Settings
from docflow.db import Database
from docflow.photos import MockPhotosLibrary


@pytest.mark.e2e
class TestE2EScheduler:
    def test_scheduler_creates_and_starts(self, e2e_settings: Settings):
        """Scheduler starts without errors and registers the job."""
        from docflow.scheduler import start_scheduler

        scheduler = start_scheduler(e2e_settings)
        try:
            assert scheduler.running
            jobs = scheduler.get_jobs()
            assert len(jobs) == 1
            job = jobs[0]
            assert job.id == "daily_pipeline"
            assert job.name == "DocFlow daily pipeline"
        finally:
            scheduler.shutdown(wait=False)

    def test_scheduler_job_runs_pipeline(self, e2e_settings: Settings):
        """Scheduler job calls the pipeline and records a run in the DB."""
        from docflow.scheduler import _run_pipeline_sync

        # Run the sync wrapper with mocked Photos; pipeline runs for real (no photos → success)
        with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([])):
            with patch("docflow.pipeline.get_llm_provider", return_value=MagicMock()):
                _run_pipeline_sync(e2e_settings)

        # Verify a run was recorded in the DB
        db = Database(e2e_settings.db_path)
        runs = db.list_runs()
        assert len(runs) >= 1

    def test_scheduler_trigger_hour_minute(self, e2e_settings: Settings):
        """Cron trigger reflects configured hour/minute."""
        from apscheduler.triggers.cron import CronTrigger

        from docflow.scheduler import start_scheduler

        settings = e2e_settings.model_copy(update={"schedule_hour": 3, "schedule_minute": 30})
        scheduler = start_scheduler(settings)
        try:
            job = scheduler.get_jobs()[0]
            trigger = job.trigger
            assert isinstance(trigger, CronTrigger)
            # Check the fields — APScheduler stores them as field objects
            fields = {f.name: f for f in trigger.fields}
            assert str(fields["hour"]) == "3"
            assert str(fields["minute"]) == "30"
        finally:
            scheduler.shutdown(wait=False)

    def test_full_pipeline_run_via_sync_wrapper(self, e2e_settings: Settings, e2e_dir: Path):
        """_run_pipeline_sync: real DB, real pipeline, mocked Photos + LLM."""
        from docflow.scheduler import _run_pipeline_sync
        from tests.conftest import make_mock_llm

        mock_llm = make_mock_llm()
        e2e_settings.ensure_dirs()

        with patch("docflow.pipeline.get_library", return_value=MockPhotosLibrary([])):
            with patch("docflow.pipeline.get_llm_provider", return_value=mock_llm):
                _run_pipeline_sync(e2e_settings)

        db = Database(e2e_settings.db_path)
        runs = db.list_runs()
        assert len(runs) == 1
        assert runs[0]["status"] == "success"
