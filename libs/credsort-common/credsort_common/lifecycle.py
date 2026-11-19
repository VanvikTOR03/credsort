"""Data lifecycle helpers (ADR-0031)."""
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from .audit import record_audit


def finish_deletion(session: Session, service: str, org_id: uuid.UUID | str, *, tombstone: bool = True) -> None:
    """Called by a service after it deleted or anonymized its data for an organization. Records the confirmation as an audit
    event (consumed by Identity) and, if requested, a tombstone so replayed events of the organization are never applied."""
    if tombstone:
        session.execute(text("insert into tombstones(org_id) values (:o) on conflict do nothing"), {"o": str(org_id)})
    record_audit(session, service, None, "data.deleted", f"service/{service}", org_id=org_id)
