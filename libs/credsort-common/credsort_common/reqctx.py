"""Per-request correlation: request id and W3C traceparent (ADR-0029, FF-F3)."""
from __future__ import annotations

import contextvars
import secrets

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_traceparent: contextvars.ContextVar[str] = contextvars.ContextVar("traceparent", default="")


def new_traceparent() -> str:
    return f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-01"


def child_traceparent(parent: str | None) -> str:
    """Keep the trace id, new span id."""
    if parent and len(parent.split("-")) == 4:
        version, trace, _span, flags = parent.split("-")
        return f"{version}-{trace}-{secrets.token_hex(8)}-{flags}"
    return new_traceparent()


def set_request(request_id_value: str, traceparent: str) -> None:
    _request_id.set(request_id_value)
    _traceparent.set(traceparent)


def request_id() -> str:
    return _request_id.get()


def traceparent() -> str:
    return _traceparent.get() or new_traceparent()
