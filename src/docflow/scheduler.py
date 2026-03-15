"""APScheduler integration for daily pipeline runs."""

from __future__ import annotations

import asyncio

import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from docflow.config import Settings

logger = structlog.get_logger(__name__)


def _run_pipeline_sync(settings: Settings) -> None:
    """Synchronous wrapper so APScheduler (background thread) can run the async pipeline."""
    from docflow.db import Database
    from docflow.pipeline import Pipeline

    logger.info("Scheduled pipeline run starting")
    settings.ensure_dirs()
    db = Database(settings.db_path)
    pipeline = Pipeline(settings=settings, db=db)

    loop = asyncio.new_event_loop()
    try:
        run_id = loop.run_until_complete(pipeline.run())
        logger.info("Scheduled pipeline run complete", run_id=run_id)
    except Exception as e:
        logger.error("Scheduled pipeline run failed", error=str(e))
    finally:
        loop.close()


def start_scheduler(settings: Settings) -> BackgroundScheduler:
    """Create and start the APScheduler with a daily cron trigger."""
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _run_pipeline_sync,
        trigger=CronTrigger(hour=settings.schedule_hour, minute=settings.schedule_minute),
        args=[settings],
        id="daily_pipeline",
        name="DocFlow daily pipeline",
        replace_existing=True,
        misfire_grace_time=3600,  # Allow 1h grace if server was down
    )
    scheduler.start()
    logger.info(
        "Scheduler started",
        hour=settings.schedule_hour,
        minute=settings.schedule_minute,
    )
    return scheduler
