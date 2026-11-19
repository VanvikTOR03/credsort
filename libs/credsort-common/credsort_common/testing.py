"""Test helpers: embedded PostgreSQL, token minting, injectable Security. Used by service test suites and the dev stack."""
from __future__ import annotations

import time
import uuid
from pathlib import Path

from sqlalchemy.engine import make_url

from .db import Database
from .migrate import migrate, provision, service_urls
from .security import (Denylist, JwksCache, KeyStore, RS256Verifier, Security, ServiceAuth, CONTEXT_AUDIENCE, CONTEXT_ISSUER,
                       new_context_claims)


def start_postgres(path: Path):
    """Start an embedded PostgreSQL (pgserver). Returns (server, psycopg superuser URL)."""
    import pgserver
    server = pgserver.get_server(path, cleanup_mode="stop")
    url = make_url(server.get_uri()).set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
    return server, url


def provision_service(superuser_url: str, service: str, migrations_dir: Path) -> tuple[str, str]:
    """Create the service database + roles and run migrations. Returns (runtime_url, owner_url)."""
    provision(superuser_url, [service])
    app_url, owner_url = service_urls(superuser_url, service)
    migrate(owner_url, migrations_dir, f"{service}_app")
    return app_url, owner_url


class TestTokens:
    """Mints context tokens exactly like Identity does, for tests."""

    __test__ = False

    def __init__(self, keystore: KeyStore | None = None):
        self.keystore = keystore or KeyStore.generate()

    def token(self, *, org_id=None, org_type="SME", role="SME_ADMIN", user_id=None, org_name="Test AG", kyb="VERIFIED",
              scopes=(), on_behalf_of=None, industry="manufacturing", employees=25, now=None) -> str:
        claims = new_context_claims(user_id=user_id or uuid.uuid4(), org_id=org_id or uuid.uuid4(), org_type=org_type,
                                    org_name=org_name, role=role, scopes=scopes, on_behalf_of=on_behalf_of, kyb_status=kyb,
                                    industry=industry, employees=employees, now=now)
        return self.keystore.sign(claims)

    def headers(self, **kw) -> dict:
        return {"Authorization": f"Bearer {self.token(**kw)}"}


def make_security(service: str, tokens: TestTokens, db: Database | None = None, denylist: Denylist | None = None) -> Security:
    verifier = RS256Verifier(JwksCache.static(tokens.keystore), audience=CONTEXT_AUDIENCE, issuer=CONTEXT_ISSUER)
    return Security(service, verifier, denylist or Denylist(lambda: []), ServiceAuth(service))


def service_headers(caller: str, target: str) -> dict:
    return {"X-Service-Token": ServiceAuth(caller).issue(target)}
