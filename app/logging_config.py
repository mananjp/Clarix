"""
Structured logging configuration for Clarix.

Supports standard text logging for local dev and structured JSON logging
for production environments (activated via LOG_FORMAT=json).
"""

import os
import json
import logging
import contextvars
from datetime import datetime, timezone

# Context variable to track request correlation ID across async tasks
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class JSONLogFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects for log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            log_data["exception"] = record.exc_text
        return json.dumps(log_data)


def setup_logging(log_level: str | None = None, log_format: str | None = None) -> None:
    """Initialize application logging configuration."""
    level_name = log_level or os.getenv("LOG_LEVEL", "INFO").upper()
    format_type = log_format or os.getenv("LOG_FORMAT", "text").lower()

    level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers to prevent duplicate lines
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setLevel(level)

    if format_type == "json":
        handler.setFormatter(JSONLogFormatter())
    else:
        text_fmt = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        handler.setFormatter(logging.Formatter(text_fmt, datefmt="%Y-%m-%d %H:%M:%S"))

    root_logger.addHandler(handler)
    logging.captureWarnings(True)
