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
        app_url, _ = provision_service(pg, "notification", MIGRATIONS)
        self.db = Database(app_url, "notification")
        self.tokens = TestTokens()
        self.app = create_service_app(settings=Settings("notification", "test", app_url, "", "", False), db=self.db, security=make_security("notification", self.tokens, self.db))
        self.client = TestClient(self.app)

    def headers(self, org):
        return self.tokens.headers(org_id=org)


@pytest.fixture(scope="session")
def env(pg):  # noqa: F811
    return Env(pg)
