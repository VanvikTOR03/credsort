import sys
import uuid
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credsort_common.config import Settings
from credsort_common.db import Database
from credsort_common.pytest_fixtures import pg  # noqa: F401
from credsort_common.security import ServiceAuth
from credsort_common.testing import TestTokens, make_security, provision_service
from credsort_common.upstream import UpstreamClient

from app.main import MIGRATIONS, create_service_app

AS_OF = date(2026, 11, 19)


class FakeBilling:
    """Stands in for the Billing service (C7)."""
    def __init__(self):
        self.entitlements = ["PROFILE", "APPLY", "ADVISOR", "WHAT_IF"]
        self.fail = False
        self.calls = 0

    def get(self, path, ctx=None, **kw):
        from credsort_common.errors import UpstreamUnavailable
        self.calls += 1
        if self.fail:
            raise UpstreamUnavailable("billing down")
        return {"entitlements": self.entitlements}


class Env:
    def __init__(self, pg):
        app_url, _ = provision_service(pg, "intelligence", MIGRATIONS)
        self.db = Database(app_url, "intelligence")
        self.tokens = TestTokens()
        self.billing = FakeBilling()
        self.app = create_service_app(settings=Settings("intelligence", "test", app_url, "", "", False), db=self.db,
                                      security=make_security("intelligence", self.tokens, self.db), billing=self.billing, as_of=lambda: AS_OF)
        self.client = TestClient(self.app)

    def sme(self, **kw):
        org = uuid.uuid4()
        return org, self.tokens.headers(org_id=org, **kw)


@pytest.fixture(scope="session")
def env(pg):  # noqa: F811
    return Env(pg)
