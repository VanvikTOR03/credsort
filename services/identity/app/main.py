from __future__ import annotations

from pathlib import Path

from credsort_common.app import create_app, denylist_loader
from credsort_common.config import Settings
from credsort_common.db import Database
from credsort_common.security import (CONTEXT_AUDIENCE, CONTEXT_ISSUER, Denylist, JwksCache, KeyStore, RS256Verifier, Security,
                                       ServiceAuth)

from .api import build_router
from .consumers import deletion_tracker, kyc_runner
from .kyb import StubIdentityProvider, StubKybProvider
from .usertoken import build_user_verifier

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def create_service_app(settings: Settings | None = None, db: Database | None = None, security: Security | None = None,
                       keystore: KeyStore | None = None, kyb=None, user_verifier=None, identity_provider=None):
    keystore = keystore or KeyStore.from_env("identity")
    def own_security(database: Database) -> Security:  # Identity verifies its own tokens with its own keys, no HTTP round trip
        verifier = RS256Verifier(JwksCache.static(keystore), audience=CONTEXT_AUDIENCE, issuer=CONTEXT_ISSUER)
        return Security("identity", verifier, Denylist(denylist_loader(database)), ServiceAuth("identity"))

    app, db, sec = create_app("identity", title="Identity", migrations_dir=MIGRATIONS, settings=settings, db=db, security=security,
                              security_factory=own_security, consumers=[deletion_tracker(), kyc_runner(identity_provider or StubIdentityProvider())])
    app.include_router(build_router(db, sec, keystore, kyb or StubKybProvider(), user_verifier or build_user_verifier()))
    return app


def app_factory():
    return create_service_app()
