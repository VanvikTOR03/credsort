import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credsort_common.config import Settings
from credsort_common.db import Database
from credsort_common.pytest_fixtures import pg  # noqa: F401
from credsort_common.security import CONTEXT_AUDIENCE, JwksCache, KeyStore
from credsort_common.testing import TestTokens, make_security, provision_service, service_headers

from app.main import MIGRATIONS, create_service_app


class Env:
    def __init__(self, pg):
        app_url, _ = provision_service(pg, "billing", MIGRATIONS)
        self.db = Database(app_url, "billing")
        self.tokens = TestTokens()
        self.keystore = KeyStore.generate()
        self.app = create_service_app(settings=Settings("billing", "test", app_url, "", "", False), db=self.db,
                                      security=make_security("billing", self.tokens, self.db), keystore=self.keystore)
        self.client = TestClient(self.app)
        self.admin = self.tokens.headers(org_type="PLATFORM", role="PLATFORM_ADMIN", org_name="CredSort")
        self.svc = service_headers("marketplace", "billing")

    def new_book(self, rules, activate=True, placeholder=True):
        r = self.client.post("/v1/admin/price-books", json={"rules": rules, "placeholder": placeholder}, headers=self.admin)
        assert r.status_code == 201, r.text
        if activate:
            assert self.client.post(f"/v1/admin/price-books/{r.json()['id']}/activate", json={}, headers=self.admin).status_code == 200
        return r.json()

    def quote(self, payer_org, payer_type="SME", subject=None, basis="500000"):
        r = self.client.post("/internal/v1/quotes", json={"action": "LOAN_FUNDED", "subject_id": str(subject or uuid.uuid4()), "payer_org_id": str(payer_org),
                                                           "payer_type": payer_type, "basis": basis}, headers=self.svc)
        assert r.status_code == 201, r.text
        return r.json()

    def clear_books(self):
        with self.db.system() as s:
            s.execute(text("update price_books set status = 'SUPERSEDED' where status = 'ACTIVE'"))


@pytest.fixture(scope="session")
def env(pg):  # noqa: F811
    return Env(pg)


@pytest.fixture(autouse=True)
def _no_active_book(env):
    env.clear_books()
    yield


SME_FEE = {"code": "SME_SUCCESS", "payer": "SME", "calculator": "PERCENT_OF_PRINCIPAL", "percent": "1.0", "min_amount": "1000", "cap_amount": "8000"}
LENDER_FEE = {"code": "LENDER_SUCCESS", "payer": "LENDER", "calculator": "PERCENT_OF_PRINCIPAL", "percent": "0.75", "min_amount": "2000", "cap_amount": "7500"}

UNLOCK_FEE = {"code": "SME_UNLOCK", "payer": "SME", "trigger": "OFFERS_UNLOCKED", "calculator": "FIXED", "amount": "190"}
