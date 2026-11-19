from __future__ import annotations

from pathlib import Path

from credsort_common.app import create_app
from credsort_common.config import Settings, env
from credsort_common.db import Database
from credsort_common.security import Security

from . import service as svc
from .api import build_router
from .clients import billing_client
from .consumers import deletion_consumer, entitlement_consumer, pipeline_consumer

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def create_service_app(settings: Settings | None = None, db: Database | None = None, security: Security | None = None,
                       billing=None, as_of=None):
    kw = {"as_of": as_of} if as_of else {}
    app, db, sec = create_app("intelligence", title="Financial Intelligence", migrations_dir=MIGRATIONS, settings=settings, db=db, security=security,
                              consumers=lambda sec: [pipeline_consumer(sec, **kw), entitlement_consumer(), deletion_consumer()])
    if not env("CREDSORT_OPENAPI_ONLY"):  # contract generation needs no database
        svc.ensure_reference_data(db)
    app.include_router(build_router(db, sec, billing or billing_client(sec)))
    return app


def app_factory():
    return create_service_app()
