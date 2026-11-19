from __future__ import annotations

import threading
from pathlib import Path

from credsort_common.app import create_app
from credsort_common.config import Settings, env
from credsort_common.db import Database
from credsort_common.security import Security

from .api import build_router
from .consumers import deletion_consumer
from .worker import ImportWorker

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def create_service_app(settings: Settings | None = None, db: Database | None = None, security: Security | None = None):
    app, db, sec = create_app("accounting", title="Accounting Integration", migrations_dir=MIGRATIONS, settings=settings, db=db,
                              security=security, consumers=[deletion_consumer()])
    app.include_router(build_router(db, sec))
    # Imports run on dedicated workers (ADR-0005). `RUN_WORKER=1` starts one inside this process for single-process setups;
    # the Compose stack runs `python -m app.worker_main` as a separate deployment instead.
    if env("RUN_WORKER", "0") == "1":
        threading.Thread(target=lambda: ImportWorker(db, app.state.stop).run(), daemon=True).start()
    return app


def app_factory():
    return create_service_app()
