from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from credsort_common.app import create_app
from credsort_common.background import Consumer
from credsort_common.config import Settings
from credsort_common.db import Database
from credsort_common.security import AccessContext, Security, require_role

from . import service as svc

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
INGEST = Consumer("audit-ingest", ["*.audit.recorded.*"], svc.ingest)
DELETION = Consumer("audit-deletion", ["identity.organization.deletion_requested.*"], lambda s, e: svc.delete_org_data(s, e["credsortorgid"]))


def create_service_app(settings: Settings | None = None, db: Database | None = None, security: Security | None = None):
    app, db, sec = create_app("audit", title="Audit", migrations_dir=MIGRATIONS, settings=settings, db=db, security=security, consumers=[INGEST, DELETION])
    ctx_dep = sec.context_dependency()
    r = APIRouter()

    @r.get("/v1/activity")
    def activity(limit: int = Query(50, ge=1, le=200), before: int | None = None, ctx: AccessContext = Depends(ctx_dep)):
        if ctx.delegated and not ctx.has_scope("VIEW_PROFILE"):
            return []
        return svc.activity(db, ctx, limit, before)

    @r.get("/v1/admin/verify/{org_id}")
    def verify(org_id: uuid.UUID, ctx: AccessContext = Depends(ctx_dep)):
        require_role(ctx, "PLATFORM_ADMIN")
        with db.system() as s:
            return svc.verify_chain(s, org_id)

    app.include_router(r)
    return app


def app_factory():
    return create_service_app()
