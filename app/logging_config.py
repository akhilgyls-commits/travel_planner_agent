"""
Structured (JSON) logging setup.

Using JSON logs makes this container friendly for log aggregators
(CloudWatch, ELK, Datadog, etc.) in production, while remaining human
readable in local development via a plain formatter.
"""
import logging
import sys

from pythonjsonlogger import jsonlogger

from app.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    # Remove any pre-existing handlers (uvicorn adds its own on reload)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if settings.app_env == "production":
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s "
            "%(filename)s %(lineno)d"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )

    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Quiet down noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
