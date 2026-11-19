"""Per-service SQL migrations and database provisioning (ADR-0004: database per service, no shared tables).

Each service has `migrations/NNNN_name.sql`. The platform tables are applied first. Migrations run as the
service's owner role; the runtime role gets DML grants only (no ownership, no BYPASSRLS).
"""
from __future__ import annotations

from importlib import resources
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from .config import SERVICES


def _platform_sql() -> str:
    return resources.files("credsort_common").joinpath("sql/platform.sql").read_text()


def migrate(admin_url: str, migrations_dir: Path | str, app_role: str) -> list[str]:
    """Apply platform + service migrations. Returns the versions applied in this run."""
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
    applied: list[str] = []
    with engine.connect() as conn:
        conn.execute(text("select pg_advisory_lock(727274)"))  # one migrator at a time
        try:
            conn.execute(text(_platform_sql()))
            done = {r[0] for r in conn.execute(text("select version from schema_migrations"))}
            for path in sorted(Path(migrations_dir).glob("*.sql")):
                if path.stem in done:
                    continue
                conn.execute(text(path.read_text()))
                conn.execute(text("insert into schema_migrations(version) values (:v)"), {"v": path.stem})
                applied.append(path.stem)
            conn.execute(text(f'grant usage on schema public to "{app_role}"'))
            conn.execute(text(f'grant select, insert, update, delete on all tables in schema public to "{app_role}"'))
            conn.execute(text(f'grant usage, select on all sequences in schema public to "{app_role}"'))
            conn.execute(text(f'grant execute on all functions in schema public to "{app_role}"'))
        finally:
            conn.execute(text("select pg_advisory_unlock(727274)"))
    engine.dispose()
    return applied


def db_name(service: str) -> str:
    return f"credsort_{service}"


def provision(superuser_url: str, services: list[str] | None = None, password: str | None = None) -> None:
    """Create one database plus an owner and a runtime role per service (idempotent). Runtime roles cannot read each
    other's databases."""
    engine = create_engine(superuser_url, isolation_level="AUTOCOMMIT", future=True)
    pw = f" password '{password}'" if password else ""
    with engine.connect() as conn:
        for svc in services or SERVICES:
            for suffix in ("owner", "app"):
                role = f"{svc}_{suffix}"
                exists = conn.execute(text("select 1 from pg_roles where rolname = :r"), {"r": role}).first()
                if not exists:
                    conn.execute(text(f'create role "{role}" login{pw} nobypassrls nosuperuser'))
            name = db_name(svc)
            if not conn.execute(text("select 1 from pg_database where datname = :d"), {"d": name}).first():
                conn.execute(text(f'create database "{name}" owner "{svc}_owner"'))
            conn.execute(text(f'revoke all on database "{name}" from public'))
            conn.execute(text(f'grant connect on database "{name}" to "{svc}_owner", "{svc}_app"'))
    engine.dispose()


def service_urls(superuser_url: str, service: str, password: str | None = None) -> tuple[str, str]:
    """(runtime_url, owner_url) derived from a superuser URL. Works for TCP and unix-socket URLs."""
    base = make_url(superuser_url)
    def build(role: str):
        return base.set(drivername="postgresql+psycopg", username=role, password=password, database=db_name(service))
    return build(f"{service}_app").render_as_string(hide_password=False), build(f"{service}_owner").render_as_string(hide_password=False)
