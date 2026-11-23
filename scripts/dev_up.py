#!/usr/bin/env python
"""Runs the whole CredSort backend locally WITHOUT Docker (for machines that cannot run Compose).

* embedded PostgreSQL (pgserver) with one database and one role per service (same isolation as the Compose stack)
* a database-backed broker with RabbitMQ semantics (refused in prod)
* every service as its own process, plus the accounting import worker

The Compose stack in deploy/compose is the reference deployment (RabbitMQ, Keycloak, real Postgres).
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / ".dev"
sys.path.insert(0, str(ROOT / "libs" / "credsort-common"))

from credsort_common.config import PORTS, SERVICES  # noqa: E402
from credsort_common.migrate import provision, service_urls  # noqa: E402


def load_dotenv(path: Path) -> None:
    """Minimal .env reader: KEY=VALUE lines; existing environment variables win. The file is git-ignored and never printed."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    load_dotenv(ROOT / ".env")
    (DEV / "logs").mkdir(parents=True, exist_ok=True)
    (DEV / "keys").mkdir(parents=True, exist_ok=True)
    import pgserver
    server = pgserver.get_server(DEV / "pg", cleanup_mode="stop")
    superuser = make_url(server.get_uri()).set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
    provision(superuser)
    engine = create_engine(superuser, isolation_level="AUTOCOMMIT")
    with engine.connect() as c:
        if not c.execute(text("select 1 from pg_database where datname = 'credsort_devbroker'")).first():
            c.execute(text('create database "credsort_devbroker"'))
    engine.dispose()
    broker = "pgdev://" + make_url(superuser).set(database="credsort_devbroker").render_as_string(hide_password=False)

    base_env = {**os.environ, "CREDSORT_ENV": "dev", "PYTHONUNBUFFERED": "1", "BROKER_URL": broker, "CREDSORT_KEY_DIR": str(DEV / "keys"),
                "DEV_SUPERUSER_URL": superuser, "SERVICE_AUTH_MODE": "dev", "USER_AUTH_MODE": "dev"}
    procs: list[tuple[str, subprocess.Popen]] = []

    def spawn(name: str, cwd: Path, cmd: list[str], extra: dict) -> None:
        log = open(DEV / "logs" / f"{name}.log", "w")
        procs.append((name, subprocess.Popen(cmd, cwd=cwd, env={**base_env, **extra, "PYTHONPATH": str(cwd)}, stdout=log, stderr=subprocess.STDOUT)))

    for svc in SERVICES:
        app_url, owner_url = service_urls(superuser, svc)
        env = {"DATABASE_URL": app_url, "DATABASE_ADMIN_URL": owner_url}
        spawn(svc, ROOT / "services" / svc, [sys.executable, "-m", "uvicorn", "app.main:app_factory", "--factory", "--host", "127.0.0.1",
                                              "--port", str(PORTS[svc]), "--log-level", "warning"], env)
        if svc == "accounting":  # imports run on a separate worker deployment (ADR-0005)
            spawn("accounting-worker", ROOT / "services" / svc, [sys.executable, "-m", "app.worker_main"], env)

    def shutdown(*_):
        for _, p in procs:
            p.terminate()
        for _, p in procs:
            try:
                p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                p.kill()
        server.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    deadline = time.time() + 90
    pending = set(SERVICES)
    while pending and time.time() < deadline:
        for svc in sorted(pending):
            try:
                if httpx.get(f"http://127.0.0.1:{PORTS[svc]}/ready", timeout=1.0).status_code == 200:
                    pending.discard(svc)
            except httpx.HTTPError:
                pass
        dead = [n for n, p in procs if p.poll() is not None]
        if dead:
            print(f"service(s) exited early: {dead}; see {DEV / 'logs'}", flush=True)
            shutdown()
        time.sleep(0.5)
    if pending:
        print(f"services did not become ready: {sorted(pending)}; see {DEV / 'logs'}", flush=True)
        shutdown()
    print("backend ready: " + ", ".join(f"{s}:{PORTS[s]}" for s in SERVICES), flush=True)
    if "--no-seed" not in sys.argv:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "seed.py")], env=base_env, cwd=ROOT)
        print("seed " + ("done" if r.returncode == 0 else f"FAILED ({r.returncode})"), flush=True)
    (DEV / "ready").write_text("1")
    while True:
        dead = [n for n, p in procs if p.poll() is not None]
        if dead:
            print(f"service(s) exited: {dead}", flush=True)
            shutdown()
        time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
