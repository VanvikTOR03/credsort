from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text

from credsort_common.app import create_app
from credsort_common.background import Consumer
from credsort_common.config import Settings
from credsort_common.db import Database, set_context
from credsort_common.errors import NotFound
from credsort_common.lifecycle import finish_deletion
from credsort_common.security import AccessContext, Security

from .rules import RULES, WITHDRAW_FOR_LENDERS

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
SVC = "notification"


def handle(session, event: dict) -> None:
    name = event["type"].removeprefix("credsort.").removesuffix(".v1")
    set_context(session, None, "SYSTEM")  # this service writes the inbox of other organizations by design
    if name in WITHDRAW_FOR_LENDERS:  # revoked consent removes every lender-facing trace of the application (ADR-0008)
        d = event["data"]
        session.execute(text("delete from notifications where resource_ref = :r and org_id <> :sme"), {"r": d["application_id"], "sme": d["sme_org_id"]})
        return
    rule = RULES.get(name)
    if not rule:
        return
    for n in rule(event["data"]):
        session.execute(text("insert into notifications(id, org_id, kind, title, body, link, resource_ref) values (:i, :o, :k, :t, :b, :l, :r)"),
                        {"i": uuid.uuid4(), "o": n["org"], "k": n["kind"], "t": n["title"], "b": n["body"], "l": n["link"], "r": n["ref"]})


def delete_org_data(session, org_id) -> None:
    set_context(session, None, "SYSTEM")
    session.execute(text("delete from notifications where org_id = :o"), {"o": org_id})
    finish_deletion(session, SVC, org_id)


CONSUMERS = [Consumer("notification-inbox", [f"{n}.*" for n in [*RULES, *WITHDRAW_FOR_LENDERS]], handle),
             Consumer("notification-deletion", ["identity.organization.deletion_requested.*"], lambda s, e: delete_org_data(s, e["credsortorgid"]))]


def create_service_app(settings: Settings | None = None, db: Database | None = None, security: Security | None = None):
    app, db, sec = create_app("notification", title="Notification", migrations_dir=MIGRATIONS, settings=settings, db=db, security=security, consumers=CONSUMERS)
    ctx_dep = sec.context_dependency()
    r = APIRouter()

    @r.get("/v1/notifications")
    def list_(unread: bool = False, ctx: AccessContext = Depends(ctx_dep)):
        with db.session(ctx.effective_org_id) as s:
            rows = s.execute(text("select id, kind, title, body, link, created_at, read_at from notifications where (:u = false or read_at is null) "
                                  "order by created_at desc limit 50"), {"u": unread}).all()
            unread_count = s.execute(text("select count(*) from notifications where read_at is null")).scalar()
        return {"unread": unread_count, "items": [dict(x._mapping) for x in rows]}

    @r.post("/v1/notifications/{nid}/read", status_code=204)
    def read(nid: uuid.UUID, ctx: AccessContext = Depends(ctx_dep)):
        with db.session(ctx.effective_org_id) as s:
            if not s.execute(text("update notifications set read_at = coalesce(read_at, now()) where id = :i returning id"), {"i": nid}).first():
                raise NotFound("notification not found")

    @r.post("/v1/notifications/read-all", status_code=204)
    def read_all(ctx: AccessContext = Depends(ctx_dep)):
        with db.session(ctx.effective_org_id) as s:
            s.execute(text("update notifications set read_at = now() where read_at is null"))

    app.include_router(r)
    return app


def app_factory():
    return create_service_app()
