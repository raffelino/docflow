"""Entry point: starts the web server and scheduler together."""

import logging

import structlog
import uvicorn

from docflow.config import get_settings
from docflow.scheduler import start_scheduler
from docflow.web.app import create_app

logger = structlog.get_logger(__name__)


def main() -> None:
    settings = get_settings()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )

    scheduler = start_scheduler(settings)
    app = create_app(settings)

    logger.info(
        "Starting DocFlow",
        host=settings.web_host,
        port=settings.web_port,
        schedule=f"{settings.schedule_hour:02d}:{settings.schedule_minute:02d}",
    )

    try:
        uvicorn.run(
            app,
            host=settings.web_host,
            port=settings.web_port,
            log_level="info",
        )
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
