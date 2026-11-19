from __future__ import annotations

from pathlib import Path

from credsort_common.app import create_app
from credsort_common.config import Settings
from credsort_common.db import Database
from credsort_common.security import Security

from .api import build_router
from .clients import billing_client, intelligence_client, quote_verifier
from .consumers import consumers

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def create_service_app(settings: Settings | None = None, db: Database | None = None, security: Security | None = None,
                       intelligence=None, billing=None, quotes=None):
    app, db, sec = create_app("marketplace", title="Marketplace", migrations_dir=MIGRATIONS, settings=settings, db=db, security=security, consumers=consumers())
    app.include_router(build_router(db, sec, intelligence or intelligence_client(sec), billing or billing_client(sec), quotes or quote_verifier()))
    return app


def app_factory():
    return create_service_app()
