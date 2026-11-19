import datetime as dt
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credsort_common.config import Settings
from credsort_common.db import Database
from credsort_common.errors import UpstreamUnavailable
from credsort_common.pytest_fixtures import pg  # noqa: F401
from credsort_common.security import JwksCache, KeyStore, RS256Verifier, context_from_claims
from credsort_common.testing import TestTokens, make_security, provision_service

from app.main import MIGRATIONS, create_service_app

AS_OF = "2026-11-19"
SUMMARY = ["requested_amount", "term_months", "industry", "assessment_category", "confidence_band", "revenue_band"]


class FakeIntelligence:
    DEFAULTS = {"assessment_category": "B", "assessment_score": 62, "confidence_band": "MEDIUM", "revenue_band": "1-5M", "revenue": "2400000",
                "revenue_growth": "0.12", "ebitda_margin": "0.18", "net_profit_margin": "0.06", "current_ratio": "1.4", "working_capital": "300000",
                "equity_ratio": "0.35", "debt_to_ebitda": "2.5", "dscr": "1.6"}

    def __init__(self):
        self.values, self.fail, self.calls = dict(self.DEFAULTS), False, []

    def get(self, path, ctx=None, params=None, **kw):
        self.calls.append((path, params))
        if self.fail:
            raise UpstreamUnavailable("intelligence down")
        fields = (params or {})["fields"].split(",")
        return {"assessment_id": path.split("/")[4], "as_of": AS_OF, "fields": {f: self.values.get(f) for f in fields}}


class FakeBilling:
    """Issues signed quotes like the Billing service does: 1% of the basis, min 1000, cap 8000, payer-specific."""

    def __init__(self, keystore: KeyStore):
        self.keystore, self.fail, self.calls, self.unpriced = keystore, False, [], False

    def post(self, path, json=None, **kw):
        self.calls.append(json)
        if self.fail:
            raise UpstreamUnavailable("billing down")
        basis = Decimal(json["basis"])
        amount = Decimal(0) if self.unpriced else min(max(basis / 100, Decimal(1000)), Decimal(8000))
        qid, now = uuid.uuid4(), int(dt.datetime.now(dt.timezone.utc).timestamp())
        claims = {"iss": "credsort-billing", "aud": "credsort-quotes", "iat": now, "exp": now + 86400, "qid": str(qid), "act": json["action"],
                  "sub": json["subject_id"], "payer": json["payer_org_id"], "ptype": json["payer_type"], "basis": json["basis"], "amount": format(amount, "f"),
                  "pricing": "UNPRICED" if self.unpriced else "PRICED"}
        return {"quote_id": str(qid), "token": self.keystore.sign(claims), "amount": format(amount, "f"), "pricing": claims["pricing"]}


class Env:
    def __init__(self, pg):
        app_url, self.owner_url = provision_service(pg, "marketplace", MIGRATIONS)
        self.app_url = app_url
        self.db = Database(app_url, "marketplace")
        self.tokens = TestTokens()
        self.billing_keys = KeyStore.generate()
        self.intel, self.billing = FakeIntelligence(), FakeBilling(self.billing_keys)
        self.quotes = RS256Verifier(JwksCache.static(self.billing_keys), audience="credsort-quotes", issuer="credsort-billing")
        self.security = make_security("marketplace", self.tokens, self.db)
        self.app = create_service_app(settings=Settings("marketplace", "test", app_url, "", "", False), db=self.db, security=self.security,
                                      intelligence=self.intel, billing=self.billing, quotes=self.quotes)
        self.client = TestClient(self.app)

    # ---- actors ----
    def sme(self, role="SME_ADMIN", kyb="VERIFIED", **kw):
        org = uuid.uuid4()
        return org, self.tokens.headers(org_id=org, org_type="SME", role=role, kyb=kyb, org_name=f"Muster {org.hex[:4]} AG", **kw)

    def lender(self, kyb="VERIFIED", role="LENDER_ADMIN"):
        org = uuid.uuid4()
        return org, self.tokens.headers(org_id=org, org_type="LENDER", role=role, kyb=kyb, org_name=f"Bank {org.hex[:4]}", industry=None, employees=None)

    def ctx(self, headers):
        return context_from_claims(self.security.context_verifier.verify(headers["Authorization"].split()[1]), headers["Authorization"].split()[1])

    def as_owner(self, sql: str, **params):
        """Test set-up the runtime role may not do (it cannot disable triggers or delete benchmark rows)."""
        from sqlalchemy import create_engine
        engine = create_engine(self.owner_url, isolation_level="AUTOCOMMIT")
        with engine.connect() as c:
            c.execute(text("select set_config('app.role', 'SYSTEM', false)"))  # FORCE RLS applies to the owner too: act as the platform
            for stmt in sql.split(";"):
                if stmt.strip():
                    c.execute(text(stmt), params)
        engine.dispose()

    # ---- flows ----
    def draft(self, headers, amount="500000", term=60, **kw):
        r = self.client.post("/v1/applications", json={"amount": amount, "term_months": term, "assessment_id": str(uuid.uuid4()), "purpose": "Expansion", **kw}, headers=headers)
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def publish(self, headers, app_id=None, fields=SUMMARY, lenders=None, **kw):
        app_id = app_id or self.draft(headers, **kw)
        r = self.client.post(f"/v1/applications/{app_id}/publication", json={"fields": fields, "lender_org_ids": lenders and [str(x) for x in lenders]}, headers=headers)
        assert r.status_code == 201, r.text
        return app_id

    def criteria(self, headers, **crit):
        r = self.client.put("/v1/lender/criteria", json={"criteria": crit}, headers=headers)
        assert r.status_code == 200, r.text

    def matches(self, headers):
        r = self.client.get("/v1/lender/matches", headers=headers)
        assert r.status_code == 200, r.text
        return r.json()

    def offer(self, headers, app_id, amount="500000", rate="3.2", term=60, days=30, **kw):
        body = {"amount": amount, "rate": rate, "term_months": term, "fees": "1500", "repayment": "LINEAR", "valid_until": str(dt.date.today() + dt.timedelta(days=days)), **kw}
        return self.client.post(f"/v1/lender/applications/{app_id}/offers", json=body, headers=headers)

    def events(self, kind, org=None):
        with self.db.system() as s:
            rows = s.execute(text("select payload from outbox where event_type like :t order by created_at, id"), {"t": f"%{kind}%"}).all()
        return [r.payload for r in rows if org is None or r.payload["credsortorgid"] == str(org)]


@pytest.fixture(scope="session")
def env(pg):  # noqa: F811
    return Env(pg)


@pytest.fixture(autouse=True)
def _reset_fakes(env):
    env.intel.values, env.intel.fail, env.intel.calls = dict(FakeIntelligence.DEFAULTS), False, []
    env.billing.fail, env.billing.unpriced, env.billing.calls = False, False, []
    yield
