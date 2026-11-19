"""Environment-driven configuration shared by all services."""
from __future__ import annotations

import os
from dataclasses import dataclass

SERVICES = ["identity", "accounting", "intelligence", "marketplace", "billing", "advisory", "notification", "audit"]
PORTS = {
    "identity": 8001, "accounting": 8002, "intelligence": 8003, "marketplace": 8004,
    "billing": 8005, "advisory": 8006, "notification": 8007, "audit": 8008, "web": 3000,
}


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def environment() -> str:
    """dev | test | prod. Dev-only shortcuts (dev login, dev broker, HMAC service tokens) are refused in prod."""
    return env("CREDSORT_ENV", "dev") or "dev"


def is_prod() -> bool:
    return environment() == "prod"


def service_url(name: str) -> str:
    return env(f"{name.upper()}_URL", f"http://127.0.0.1:{PORTS[name]}") or ""


@dataclass(frozen=True)
class Settings:
    service: str
    environment: str
    database_url: str
    database_admin_url: str
    broker_url: str
    run_background: bool

    @classmethod
    def from_env(cls, service: str) -> "Settings":
        return cls(
            service=service,
            environment=environment(),
            database_url=env("DATABASE_URL", "") or "",
            database_admin_url=env("DATABASE_ADMIN_URL", "") or "",
            broker_url=env("BROKER_URL", "") or "",
            run_background=(env("RUN_BACKGROUND", "1") == "1"),
        )
