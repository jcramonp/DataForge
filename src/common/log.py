"""Structured logging with pipeline run context.

Every log line emitted inside ``run_context(...)`` carries the bound
identifiers (``run_id``, ``dataset``, ``stage``, ``client``, ...), so a failed
pipeline can be traced from logs to its ``pipeline_run`` row and dataset.

Format is selected by ``DATAFORGE_LOG_FORMAT``: ``json`` (one JSON object per
line, default outside local) or ``text`` (human readable, default locally).
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from src.common.settings import Settings, get_settings


_CONTEXT: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "dataforge_log_context",
    default={},
)

_HANDLER_MARKER = "_dataforge_handler"

_SENSITIVE_KEYS = ("password", "secret", "token", "authorization", "api_key")

# Attributes every LogRecord has; anything else was passed through ``extra``.
_STANDARD_ATTRS = set(
    vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys()
) | {"message", "asctime", "context"}


def _redact(key: str, value: Any) -> Any:
    if any(marker in key.lower() for marker in _SENSITIVE_KEYS):
        return "***"
    return value


def current_context() -> dict[str, Any]:
    return dict(_CONTEXT.get())


@contextmanager
def run_context(**fields: Any) -> Iterator[dict[str, Any]]:
    """Bind identifiers to every log record emitted inside the block."""

    merged = {**_CONTEXT.get(), **{k: v for k, v in fields.items() if v is not None}}
    token = _CONTEXT.set(merged)
    try:
        yield merged
    finally:
        _CONTEXT.reset(token)


def bind_context(**fields: Any) -> None:
    """Add identifiers to the active context (e.g. once ``run_id`` is known)."""

    _CONTEXT.set({**_CONTEXT.get(), **{k: v for k, v in fields.items() if v is not None}})


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.context = current_context()
        return True


def _record_fields(record: logging.LogRecord) -> dict[str, Any]:
    fields = dict(getattr(record, "context", {}) or {})
    for key, value in vars(record).items():
        if key not in _STANDARD_ATTRS and not key.startswith("_"):
            fields[key] = value
    return {key: _redact(key, value) for key, value in fields.items()}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_record_fields(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(name)s %(context_text)s%(message)s")

    def format(self, record: logging.LogRecord) -> str:
        fields = _record_fields(record)
        record.context_text = (
            "[" + " ".join(f"{k}={v}" for k, v in fields.items()) + "] "
            if fields
            else ""
        )
        return super().format(record)


def configure_logging(settings: Settings | None = None, *, force: bool = False) -> None:
    """Install the DataForge handler on the root logger (idempotent)."""

    settings = settings or get_settings()
    root = logging.getLogger()

    existing = [h for h in root.handlers if getattr(h, _HANDLER_MARKER, False)]
    if existing and not force:
        return
    for handler in existing:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    setattr(handler, _HANDLER_MARKER, True)
    handler.addFilter(ContextFilter())
    handler.setFormatter(
        JsonFormatter() if settings.log_format == "json" else TextFormatter()
    )

    root.addHandler(handler)
    root.setLevel(settings.log_level)

    # Third-party clients are noisy at INFO and may log request details.
    for noisy in ("botocore", "boto3", "urllib3", "s3transfer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
