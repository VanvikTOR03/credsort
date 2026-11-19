from __future__ import annotations

from pathlib import Path

from credsort_common.app import create_app
from credsort_common.config import Settings
from credsort_common.db import Database
from credsort_common.security import KeyStore, Security

from .api import build_router
from .consumers import consumers

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def create_service_app(settings: Settings | None = None, db: Database | None = None, security: Security | None = None, keystore: KeyStore | None = None):
    keystore = keystore or KeyStore.from_env("billing")
    app, db, sec = create_app("billing", title="Billing", migrations_dir=MIGRATIONS, settings=settings, db=db, security=security, consumers=consumers())
    app.include_router(build_router(db, sec, keystore))
    return app


def app_factory():
    return create_service_app()
