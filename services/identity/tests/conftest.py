import sys
import time
import uuid
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credsort_common.config import Settings
from credsort_common.db import Database
from credsort_common.pytest_fixtures import pg  # noqa: F401
from credsort_common.security import KeyStore
from credsort_common.testing import TestTokens, make_security, provision_service

from app.main import MIGRATIONS, create_service_app
from app.usertoken import DevUserVerifier

SECRET = "test-user-secret-0123456789-0123456789"


class Env:
    def __init__(self, pg):
        app_url, self.owner_url = provision_service(pg, "identity", MIGRATIONS)
        self.db = Database(app_url, "identity")
        self.keystore = KeyStore.generate()
        self.tokens = TestTokens(self.keystore)
        settings = Settings("identity", "test", app_url, "", "", False)
        self.app = create_service_app(settings=settings, db=self.db, security=make_security("identity", self.tokens, self.db),
                                      keystore=self.keystore, user_verifier=DevUserVerifier(SECRET))
        self.client = TestClient(self.app)

    def user_token(self, email, name="Test User", sub=None):
        now = int(time.time())
        return jwt.encode({"sub": sub or f"dev:{email}", "email": email, "name": name, "aud": "credsort-identity-dev", "iat": now, "exp": now + 600},
                          SECRET, algorithm="HS256")

    def user(self, email):
        return {"Authorization": f"Bearer {self.user_token(email)}"}

    def onboard(self, email, **body):
        r = self.client.post("/v1/organizations", json=body, headers=self.user(email))
        assert r.status_code == 201, r.text
        return r.json()

    def ctx_headers(self, email, org_id=None, on_behalf_of=None):
        r = self.client.post("/v1/context-tokens", json={"org_id": str(org_id) if org_id else None, "on_behalf_of": str(on_behalf_of) if on_behalf_of else None},
                             headers=self.user(email))
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()


@pytest.fixture(scope="session")
def env(pg):  # noqa: F811
    return Env(pg)


def uniq(prefix="u"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.test"
