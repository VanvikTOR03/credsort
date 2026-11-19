"""Structured logging with an allowlist of fields (ADR-0029, FF-C6): never bodies, tokens or business values."""
from __future__ import annotations

import json
import logging
import sys
import time

from .reqctx import request_id

ALLOWED_EXTRA = {"service", "event_id", "event_type", "job_id", "status", "duration_ms", "path", "method", "org_id", "code", "attempt"}


class AllowlistJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)), "level": record.levelname,
                 "logger": record.name, "msg": record.getMessage(), "request_id": request_id()}
        for key in ALLOWED_EXTRA:
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info).splitlines()[-1]
        return json.dumps(entry)


def configure(service: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(AllowlistJsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").disabled = True  # access logs carry paths with ids only, middleware logs instead
