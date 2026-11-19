"""Database access with row-level-security context (ADR-0004, ADR-0017).

Every transaction sets `app.org_id` and `app.role`; PostgreSQL policies use them. Roles:
USER (request on behalf of an organization), EVENT (event handler for one organization),
SYSTEM (relay, workers, reconciliation) and PLATFORM (Identity admin only).
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


class Database:
    def __init__(self, url: str, service: str):
        self.service = service
        self.engine = create_engine(url, pool_size=8, max_overflow=8, pool_pre_ping=True, future=True)

    @contextmanager
    def session(self, org_id: uuid.UUID | str | None = None, role: str = "USER") -> Iterator[Session]:
        with Session(self.engine, expire_on_commit=False) as s:
            with s.begin():
                set_context(s, org_id, role)
                yield s

    def system(self):
        return self.session(None, "SYSTEM")

    def dispose(self) -> None:
        self.engine.dispose()


def set_context(session: Session, org_id: uuid.UUID | str | None, role: str) -> None:
    session.execute(
        text("select set_config('app.org_id', :o, true), set_config('app.role', :r, true)"),
        {"o": str(org_id) if org_id else "", "r": role},
    )


def set_org(session: Session, org_id: uuid.UUID | str) -> None:
    """Switch the RLS organization inside an event handler (e.g. to write for another tenant)."""
    session.execute(text("select set_config('app.org_id', :o, true)"), {"o": str(org_id)})
