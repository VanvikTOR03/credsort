import sys
import uuid
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credsort_common.config import Settings
from credsort_common.db import Database
from credsort_common.pytest_fixtures import pg  # noqa: F401
from credsort_common.testing import TestTokens, make_security, provision_service, service_headers

from app.main import MIGRATIONS, create_service_app

AS_OF = date(2026, 11, 19)


class Env:
    def __init__(self, pg):
        app_url, _ = provision_service(pg, "accounting", MIGRATIONS)
        self.db = Database(app_url, "accounting")
        self.tokens = TestTokens()
        self.app = create_service_app(settings=Settings("accounting", "test", app_url, "", "", False), db=self.db,
                                      security=make_security("accounting", self.tokens, self.db))
        self.client = TestClient(self.app)

    def sme(self, org=None, **kw):
        org = org or uuid.uuid4()
        return org, self.tokens.headers(org_id=org, **kw)

    def connect(self, headers, dataset="muster", source="SYNTHETIC"):
        r = self.client.post("/v1/connections", json={"source_type": source, "dataset": dataset}, headers=headers)
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def start(self, headers, connection_id, **extra):
        return self.client.post("/v1/import-jobs", json={"connection_id": connection_id}, headers={**headers, **extra})


@pytest.fixture(scope="session")
def env(pg):  # noqa: F811
    return Env(pg)


@pytest.fixture(autouse=True)
def _no_leftover_jobs(env):
    """Jobs left in flight by one test must not be claimed by the next one."""
    from sqlalchemy import text
    with env.db.system() as s:
        s.execute(text("update import_jobs set status = 'FAILED', failure_reason = 'TEST_CLEANUP', finished_at = now() where status in ('PENDING','RUNNING')"))
    yield
