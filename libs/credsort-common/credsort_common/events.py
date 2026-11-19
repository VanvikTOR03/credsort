"""CloudEvents 1.0 envelope, strict validation and the transactional outbox writer (ADR-0023)."""
from __future__ import annotations

import datetime as dt
import json
import uuid
from decimal import Decimal
from functools import lru_cache

from jsonschema import Draft202012Validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from .event_catalog import CATALOG, event_type
from .reqctx import traceparent


def jsonable(value):
    """Convert UUID/date/Decimal into JSON-safe values (decimals stay strings, ADR-0015)."""
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


@lru_cache(maxsize=None)
def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(CATALOG[name])


def build_event(service: str, name: str, org_id, subject: str, data: dict, version: int = 1) -> dict:
    if name not in CATALOG:
        raise KeyError(f"unknown event {name}")
    data = jsonable(data)
    errors = sorted(_validator(name).iter_errors(data), key=lambda e: list(e.path))
    if errors:
        raise ValueError(f"event {name} violates its schema: {errors[0].message}")
    return {
        "specversion": "1.0", "id": str(uuid.uuid4()), "type": event_type(name), "source": f"/services/{service}",
        "subject": subject, "time": dt.datetime.now(dt.timezone.utc).isoformat(), "datacontenttype": "application/json",
        "credsortorgid": str(org_id), "credsortaggregateversion": version, "traceparent": traceparent(), "data": data,
    }


def emit(session: Session, service: str, name: str, org_id, subject: str, data: dict, version: int = 1) -> dict:
    """Write an event to the outbox in the caller's transaction. This is the ONLY way to publish (R-I13)."""
    event = build_event(service, name, org_id, subject, data, version)
    session.execute(
        text("insert into outbox(id, event_type, org_id, subject, aggregate_version, payload) "
             "values (:id, :t, :o, :s, :v, cast(:p as jsonb))"),
        {"id": event["id"], "t": event["type"], "o": str(org_id), "s": subject, "v": version, "p": json.dumps(event)},
    )
    return event
