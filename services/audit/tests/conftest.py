import datetime as dt
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credsort_common.config import Settings
from credsort_common.db import Database
from credsort_common.pytest_fixtures import pg  # noqa: F401
from credsort_common.testing import TestTokens, make_security, provision_service

from app.main import MIGRATIONS, create_service_app


class Env:
    def __init__(self, pg):
        app_url, self.owner_url = provision_service(pg, "audit", MIGRATIONS)
        self.db = Database(app_url, "audit")
        self.tokens = TestTokens()
        self.app = create_service_app(settings=Settings("audit", "test", app_url, "", "", False), db=self.db, security=make_security("audit", self.tokens, self.db))
        self.client = TestClient(self.app)

    def event(self, org, action="offer.selected", service="marketplace", actor=None, acting=None, behalf=None, resource="offer/x"):
        return {"id": str(uuid.uuid4()), "type": f"credsort.{service}.audit.recorded.v1", "source": f"/services/{service}", "credsortorgid": str(org),
                "time": dt.datetime.now(dt.timezone.utc).isoformat(),
                "data": {"audit_id": str(uuid.uuid4()), "actor_user_id": str(actor) if actor else None, "acting_org_id": str(acting) if acting else None,
                         "on_behalf_of_org_id": str(behalf) if behalf else None, "action": action, "resource": resource}}


@pytest.fixture(scope="session")
def env(pg):  # noqa: F811
    return Env(pg)
