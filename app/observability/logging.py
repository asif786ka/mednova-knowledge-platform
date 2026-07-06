"""
Observability: structured JSON logging, latency timing, request ids, and optional
Langfuse tracing. Everything degrades gracefully when Langfuse is not configured.
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Any

from app.config import settings

_LANGFUSE = None


def _init_langfuse():
    global _LANGFUSE
    if _LANGFUSE is not None:
        return _LANGFUSE
    if not settings.langfuse_enabled:
        _LANGFUSE = False
        return _LANGFUSE
    try:  # pragma: no cover - only when keys present
        from langfuse import Langfuse

        _LANGFUSE = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
        )
    except Exception:
        _LANGFUSE = False
    return _LANGFUSE


def langfuse_client():
    client = _init_langfuse()
    return client or None


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "extra_fields"):
            payload.update(record.extra_fields)  # type: ignore[attr-defined]
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_CONFIGURED = False


def _configure_root():
    global _CONFIGURED
    if _CONFIGURED:
        return
    # stdout by default; MCP stdio servers set LOG_STREAM=stderr so structured logs never
    # corrupt the JSON-RPC protocol stream (which owns stdout).
    import os

    stream = sys.stderr if os.getenv("LOG_STREAM", "stdout").lower() == "stderr" else sys.stdout
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("mednova")
    root.handlers = [handler]
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_root()
    return logging.getLogger(f"mednova.{name}")


def log(logger: logging.Logger, level: str, msg: str, **fields: Any) -> None:
    """Structured log helper: attaches arbitrary fields to the JSON record."""
    rec_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(rec_level, msg, extra={"extra_fields": fields})


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


class Timer:
    """Context manager that measures elapsed wall-clock time in milliseconds."""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        self.ms = 0.0
        return self

    def __exit__(self, *exc: Any) -> None:
        self.ms = round((time.perf_counter() - self._start) * 1000, 1)


@contextmanager
def trace_event(name: str, request_id: str | None = None, **metadata: Any):
    """
    Lightweight tracing span. Emits a structured log line and, when Langfuse is
    configured, records a Langfuse span. Yields a dict the caller can enrich.
    """
    logger = get_logger("trace")
    client = langfuse_client()
    span = None
    if client:  # pragma: no cover
        try:
            span = client.span(name=name, metadata=metadata)
        except Exception:
            span = None
    ctx: dict[str, Any] = {"name": name, "request_id": request_id}
    t = Timer()
    t.__enter__()
    try:
        yield ctx
    finally:
        t.__exit__()
        ctx["latency_ms"] = t.ms
        log(logger, "INFO", f"trace:{name}", request_id=request_id,
            latency_ms=t.ms, **{k: v for k, v in metadata.items()})
        if span:  # pragma: no cover
            try:
                span.end(metadata={**metadata, "latency_ms": t.ms})
            except Exception:
                pass
