"""Structured logging setup for production deployments."""

import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger

from app.core.config import Settings


def setup_logging(settings: Settings) -> None:
    """Configure root logger with JSON lines on stdout.

    In Kubernetes or similar, stdout JSON is easy to ship to log aggregators.
    """

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(settings.log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={"levelname": "level", "asctime": "timestamp"},
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Reduce noisy third-party loggers if needed
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def log_extra(**kwargs: Any) -> dict[str, Any]:
    """Build a structured ``extra`` dict for ``logger.info(..., extra=...)``.

    JsonLogger will merge these keys into the JSON line.
    """

    return kwargs
