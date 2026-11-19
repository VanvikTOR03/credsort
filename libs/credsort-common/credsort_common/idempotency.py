"""Idempotency-Key support for mutating external endpoints (ADR-0006): stored per (organization, key) for 24 h."""
from __future__ import annotations

import hashlib
import json
from typing import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from .errors import Conflict
from .events import jsonable


def _fingerprint(source: dict) -> str:
    return hashlib.sha256(json.dumps(jsonable(source), sort_keys=True).encode()).hexdigest()


def lookup_idempotent(session: Session, org_id, key: str | None, fingerprint_source: dict) -> tuple[int, dict] | None:
    """Returns the stored response of an earlier identical request, so a replay never trips over state checks that the first
    call already changed (e.g. 'application is no longer a draft')."""
    if not key:
        return None
    row = session.execute(text("select fingerprint, status_code, response from idempotency_keys where org_id = :o and key = :k"), {"o": org_id, "k": key}).first()
    if not row:
        return None
    if row.fingerprint != _fingerprint(fingerprint_source):
        raise Conflict("Idempotency-Key was already used with a different request", code="idempotency_key_reused")
    return row.status_code, row.response


def run_idempotent(session: Session, org_id, key: str | None, fingerprint_source: dict,
                   action: Callable[[], tuple[int, dict]]) -> tuple[int, dict]:
    """Executes `action` once per key. A repeated key returns the stored response; a reused key with a different
    request body is a conflict."""
    if not key:
        return action()
    fingerprint = _fingerprint(fingerprint_source)
    session.execute(text("delete from idempotency_keys where created_at < now() - interval '24 hours'"))
    row = session.execute(text("select fingerprint, status_code, response from idempotency_keys where org_id = :o and key = :k "
                               "for update"), {"o": org_id, "k": key}).first()
    if row:
        if row.fingerprint != fingerprint:
            raise Conflict("Idempotency-Key was already used with a different request", code="idempotency_key_reused")
        return row.status_code, row.response
    status, body = action()
    session.execute(text("insert into idempotency_keys(org_id, key, fingerprint, status_code, response) "
                         "values (:o, :k, :f, :s, cast(:r as jsonb)) on conflict do nothing"),
                    {"o": org_id, "k": key, "f": fingerprint, "s": status, "r": json.dumps(jsonable(body))})
    return status, body
