import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credsort_common.config import Settings
from credsort_common.db import Database
from credsort_common.errors import UpstreamUnavailable
from credsort_common.pytest_fixtures import pg  # noqa: F401
from credsort_common.testing import TestTokens, make_security, provision_service

from app.main import MIGRATIONS, create_service_app
from app.plugins.models import TemplateModel


def metric(code, value, unit="RATIO", status="OK", reason=None):
    return {"code": code, "value": value, "unit": unit, "status": status, "reason": reason}


def factor(code, value, points, direction, weight=10):
    return {"code": code, "label": code, "value": value, "points": points, "weight": weight, "direction": direction, "note": ""}


def context(scenario=False):
    metrics = [metric("revenue", "2400000.00000000", "CHF"), metric("revenue_growth", "0.12000000"), metric("ebitda_margin", "0.18000000"), metric("net_profit_margin", "0.06000000"),
               metric("current_ratio", "0.95000000"), metric("working_capital", "-50000.00000000", "CHF"), metric("equity_ratio", "0.08000000"),
               metric("debt_to_ebitda", "4.20000000"), metric("dscr", "1.30000000"), metric("receivables_aging", None, status="UNAVAILABLE", reason="NO_INVOICE_LEVEL_DATA")]
    factors = [factor("ebitda_margin", "0.18000000", 100, "positive", 20), factor("equity_ratio", "0.08000000", 0, "negative", 20), factor("current_ratio", "0.95000000", 21, "negative", 15),
               factor("revenue_growth", "0.12000000", 100, "positive", 10), factor("dscr", None, None, "unknown", 10)]
    ctx = {"assessment": {"id": "00000000-0000-0000-0000-000000000001", "category": "C", "label": "Watch", "score": 48, "factors": factors,
                          "confidence": {"overall": "0.790", "band": "MEDIUM", "completeness": "0.900", "freshness": "1.000", "consistency": "1.000", "provenance": "0.400", "demo_data": True}},
           "period_end": "2025-12-31", "metrics": metrics, "versions": {"scorecard": "sc-1.0.0"}, "scenario": None}
    if scenario:
        after = [dict(m, value="0.30000000") if m["code"] == "equity_ratio" else m for m in metrics]
        ctx["scenario"] = {"id": "00000000-0000-0000-0000-000000000002", "inputs": {"debt_repayment_from_cash": "100000"},
                           "result": {"before": {"metrics": metrics, "assessment": {"score": 48, "category": "C"}},
                                      "after": {"metrics": after, "assessment": {"score": 61, "category": "B"}}, "assumptions": ["Debt is repaid from cash."]}}
    return ctx


class FakeIntel:
    def __init__(self):
        self.calls, self.fail, self.scenario = 0, False, False

    def get(self, path, ctx=None, params=None, **kw):
        self.calls += 1
        if self.fail:
            raise UpstreamUnavailable("down")
        return context(scenario=bool(params and params.get("scenario_id")))


class FakeBilling:
    def __init__(self):
        self.entitlements, self.fail = ["PROFILE", "APPLY", "ADVISOR", "WHAT_IF"], False

    def get(self, path, ctx=None, **kw):
        if self.fail:
            raise UpstreamUnavailable("down")
        return {"entitlements": self.entitlements}


class Env:
    def __init__(self, pg):
        app_url, _ = provision_service(pg, "advisory", MIGRATIONS)
        self.db = Database(app_url, "advisory")
        self.tokens = TestTokens()
        self.intel, self.billing, self.chain = FakeIntel(), FakeBilling(), [TemplateModel()]
        self.app = create_service_app(settings=Settings("advisory", "test", app_url, "", "", False), db=self.db, security=make_security("advisory", self.tokens, self.db),
                                      intelligence=self.intel, billing=self.billing, chain=self.chain)
        self.client = TestClient(self.app)

    def sme(self, **kw):
        org = uuid.uuid4()
        return org, self.tokens.headers(org_id=org, **kw)


@pytest.fixture(scope="session")
def env(pg):  # noqa: F811
    return Env(pg)
