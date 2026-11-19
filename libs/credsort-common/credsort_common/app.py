"""FastAPI application factory shared by all services (ADR-0001, ADR-0006, ADR-0029)."""
from __future__ import annotations

import logging
import secrets
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable, Sequence

from fastapi import FastAPI, Request
from sqlalchemy import text

from .background import Consumer, ConsumerRunner, OutboxRelay
from .broker import make_broker
from .config import Settings
from .db import Database
from .errors import install_error_handlers
from . import money  # noqa: F401  (installs the Decimal-as-string encoder)
from .logging_setup import configure
from .migrate import migrate
from .reqctx import child_traceparent, new_traceparent, set_request
from .security import Denylist, Security, build_security

log = logging.getLogger("credsort.app")


def denylist_consumer() -> Consumer:
    """Every service keeps a local deny-list of revoked memberships and suspended organizations."""
    def handle(session, event):
        data = event["data"]
        if event["type"].startswith("credsort.identity.membership.revoked"):
            session.execute(text("insert into denylist(user_id, org_id, since) values (:u, :o, :s)"),
                            {"u": data["user_id"], "o": data["org_id"], "s": data["revoked_at"]})
        elif event["type"].startswith("credsort.identity.organization.suspended"):
            session.execute(text("insert into denylist(user_id, org_id, since) values (null, :o, now())"), {"o": data["org_id"]})
        elif event["type"].startswith("credsort.identity.delegation.revoked"):  # the fiduciary loses its delegated access at once
            session.execute(text("insert into denylist(user_id, org_id, on_behalf_of, since) values (null, :f, :s, now())"),
                            {"f": data["fiduciary_org_id"], "s": data["sme_org_id"]})
    return Consumer("denylist", ["identity.membership.revoked.*", "identity.organization.suspended.*",
                                 "identity.delegation.revoked.*"], handle)


def denylist_loader(db: Database):
    def load():
        with db.system() as s:
            rows = s.execute(text("select user_id, org_id, on_behalf_of, extract(epoch from since) as since from denylist "
                                  "where since > now() - interval '1 day'")).all()
        return [(r.user_id, r.org_id, r.on_behalf_of, float(r.since)) for r in rows]
    return load


def create_app(service: str, *, title: str, migrations_dir: Path, settings: Settings | None = None, db: Database | None = None,
               security: Security | None = None, security_factory: Callable[[Database], Security] | None = None,
               consumers: Sequence[Consumer] | Callable[[Security], Sequence[Consumer]] = (), version: str = "0.1.0",
               on_startup: Callable[[], None] | None = None) -> tuple[FastAPI, Database, Security]:
    settings = settings or Settings.from_env(service)
    configure(service)
    if db is None:
        if settings.database_admin_url:
            migrate(settings.database_admin_url, migrations_dir, f"{service}_app")
        db = Database(settings.database_url, service)
    if security is None:
        security = security_factory(db) if security_factory else build_security(service, Denylist(denylist_loader(db)))
    stop = threading.Event()
    built = consumers(security) if callable(consumers) else list(consumers)  # factories get the finished Security (service clients)
    all_consumers = [denylist_consumer(), *built]

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if on_startup:
            on_startup()
        threads: list[threading.Thread] = []
        if settings.run_background and settings.broker_url:
            broker = make_broker(settings.broker_url)
            threads.append(OutboxRelay(db, broker, stop))
            threads += [ConsumerRunner(db, broker, c, stop) for c in all_consumers]
            for t in threads:
                t.start()
        yield
        stop.set()

    app = FastAPI(title=f"CredSort {title}", version=version, lifespan=lifespan,
                  docs_url="/docs", openapi_url="/openapi.json")
    install_error_handlers(app)
    app.state.service, app.state.db, app.state.security, app.state.stop = service, db, security, stop

    @app.middleware("http")
    async def correlate(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        tp = child_traceparent(request.headers.get("traceparent")) if request.headers.get("traceparent") else new_traceparent()
        set_request(rid, tp)
        started = time.time()
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        response.headers["traceparent"] = tp
        if request.url.path.startswith(("/v1", "/internal")):
            response.headers["Cache-Control"] = "no-store"
        log.info("request", extra={"service": service, "method": request.method, "path": _redact(request.url.path),
                                   "status": response.status_code, "duration_ms": int((time.time() - started) * 1000)})
        return response

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok", "service": service}

    @app.get("/ready", include_in_schema=False)
    def ready():
        with db.system() as s:
            s.execute(text("select 1"))
        return {"status": "ready", "service": service}

    return app, db, security


def _redact(path: str) -> str:
    """Log paths with ids replaced, so only the route shape is recorded."""
    import re
    return re.sub(r"[0-9a-fA-F-]{36}", "{id}", path)
