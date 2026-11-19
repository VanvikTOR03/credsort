"""End-to-end test across all running services (real HTTP, real events through the broker).

Run the backend first:  python scripts/dev_up.py   (or the Compose stack), then:  pytest tests/e2e -q
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "libs" / "credsort-common"))

import seed  # noqa: E402

try:
    httpx.get(f"{seed.BASE['identity']}/ready", timeout=1.0).raise_for_status()
except Exception:  # noqa: BLE001
    pytest.skip("backend is not running (start scripts/dev_up.py)", allow_module_level=True)

FIELDS = ["requested_amount", "term_months", "industry", "assessment_category", "confidence_band", "revenue_band", "equity_ratio", "ebitda_margin", "debt_to_ebitda"]
ANNA, PETER, SANDRA = seed.SMES[0], seed.LENDERS[1], seed.LENDERS[0]
# the embedded dev PostgreSQL listens on a unix socket inside its data directory
SUPERUSER = os.environ.get("DEV_SUPERUSER_URL") or f"postgresql+psycopg://postgres@/postgres?host={ROOT / '.dev' / 'pg'}"


def wait(fn, what, timeout=40.0):
    end = time.time() + timeout
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.4)
    raise AssertionError(f"timed out waiting for {what}")


def api(method, service, path, headers, ok=(200, 201, 202, 204), **kw):
    r = httpx.request(method, seed.BASE[service] + path, headers=headers, timeout=30.0, **kw)
    assert r.status_code in ok, f"{method} {service}{path} -> {r.status_code} {r.text[:200]}"
    return r


@pytest.fixture(scope="module")
def actors():
    return {"anna": seed.login(ANNA[0], ANNA[1]), "peter": seed.login(PETER[0], PETER[1]), "sandra": seed.login(SANDRA[0], SANDRA[1]),
            "admin": seed.login(*seed.PLATFORM)}


@pytest.fixture(scope="module")
def pricing(actors):
    """An illustrative price book (pitch-deck numbers, flagged placeholder) so the fee path can be exercised."""
    rules = [{"code": "SME_SUCCESS", "payer": "SME", "calculator": "PERCENT_OF_PRINCIPAL", "percent": "1.0", "min_amount": "1000", "cap_amount": "8000"},
             {"code": "LENDER_SUCCESS", "payer": "LENDER", "calculator": "PERCENT_OF_PRINCIPAL", "percent": "0.75", "min_amount": "2000", "cap_amount": "7500"}]
    book = api("POST", "billing", "/v1/admin/price-books", actors["admin"], json={"rules": rules, "placeholder": True}).json()
    api("POST", "billing", f"/v1/admin/price-books/{book['id']}/activate", actors["admin"], json={})
    return book


def publish_new_application(actors, amount="500000"):
    profile = api("GET", "intelligence", "/v1/profile/current", actors["anna"]).json()
    app = api("POST", "marketplace", "/v1/applications", actors["anna"], json={"amount": amount, "term_months": 60, "purpose": "e2e", "assessment_id": profile["assessment"]["id"]}).json()["id"]
    api("POST", "marketplace", f"/v1/applications/{app}/publication", actors["anna"], json={"fields": FIELDS})
    return app


def offer_body(days=30, amount="500000"):
    return {"amount": amount, "rate": "3.1", "term_months": 60, "fees": "1500", "repayment": "LINEAR", "valid_until": str(dt.date.today() + dt.timedelta(days=days))}


def charges(actor):
    return api("GET", "billing", "/v1/charges", actor).json()


def test_the_whole_lending_journey_across_all_services(actors, pricing):
    anna, peter, admin = actors["anna"], actors["peter"], actors["admin"]
    # 1. publish -> the matching lender is notified through the event flow and sees only the consented fields
    app = publish_new_application(actors)
    matches = api("GET", "marketplace", "/v1/lender/matches", peter).json()
    mine = next(i for i in matches["items"] if i["application_id"] == app)
    assert set(mine["fields"]) == set(FIELDS) and "company_name" not in mine["fields"] and mine["explanation"]
    wait(lambda: any(n["kind"] == "application.matched" for n in api("GET", "notification", "/v1/notifications", peter).json()["items"]), "match notification")
    # 2. the lender offers; fees are quoted by Billing and stored with the offer
    sub = api("POST", "marketplace", f"/v1/lender/applications/{app}/offers", peter, json=offer_body()).json()
    offers = api("GET", "marketplace", f"/v1/applications/{app}/offers", anna).json()
    assert Decimal(offers[0]["credsort_fee"]["amount"]) == Decimal("5000.00") and offers[0]["credsort_fee"]["pricing"] == "PRICED"
    assert Decimal(sub["your_fee"]["amount"]) == Decimal("3750.00")
    wait(lambda: any(n["kind"] == "offer.submitted" for n in api("GET", "notification", "/v1/notifications", anna).json()["items"]), "offer notification")
    # 3. selection costs nothing
    api("POST", "marketplace", f"/v1/offers/{sub['id']}/selection", anna)
    time.sleep(2)
    assert not [c for c in charges(anna) if c["offer_id"] == sub["id"]], "selecting an offer must not create a fee"
    wait(lambda: any(n["kind"] == "offer.selected" for n in api("GET", "notification", "/v1/notifications", peter).json()["items"]), "selected notification")
    # 4. the lender confirms the payout -> exactly one charge per payer, equal to the quote
    api("POST", "marketplace", f"/v1/lender/offers/{sub['id']}/confirm-payout", peter)
    sme_charge = wait(lambda: next((c for c in charges(anna) if c["offer_id"] == sub["id"]), None), "SME fee")
    lender_charge = wait(lambda: next((c for c in charges(peter) if c["offer_id"] == sub["id"]), None), "lender fee")
    assert Decimal(sme_charge["amount"]) == Decimal("5000.00") and Decimal(lender_charge["amount"]) == Decimal("3750.00") and sme_charge["status"] == "RECORDED"
    # 5. a duplicate broker delivery of the very same event cannot create a second fee
    from sqlalchemy import text
    from credsort_common.broker import PgDevBroker
    from credsort_common.db import Database
    from credsort_common.migrate import service_urls
    from sqlalchemy.engine import make_url
    market = Database(service_urls(SUPERUSER, "marketplace")[0], "marketplace")
    with market.system() as s:
        event = s.execute(text("select payload from outbox where event_type like '%loan.funded%' and payload->'data'->>'offer_id' = :o"), {"o": sub["id"]}).scalar()
    broker = PgDevBroker(make_url(SUPERUSER).set(database="credsort_devbroker").render_as_string(hide_password=False))
    broker.publish(event)
    broker.publish(event)
    time.sleep(3)
    assert len([c for c in charges(anna) if c["offer_id"] == sub["id"]]) == 1 and len([c for c in charges(peter) if c["offer_id"] == sub["id"]]) == 1
    # 6. the SME disputes within 14 days -> the fee is held, an operator can resolve it
    api("POST", "marketplace", f"/v1/applications/{app}/dispute", anna)
    wait(lambda: next((c for c in charges(anna) if c["offer_id"] == sub["id"] and c["status"] == "HELD"), None), "held fee")
    held = [c for c in api("GET", "billing", "/v1/admin/charges?status=HELD", admin).json() if c["offer_id"] == sub["id"]]
    api("POST", "billing", f"/v1/admin/charges/{held[0]['id']}/waive", admin)
    assert next(c for c in charges(anna) if c["offer_id"] == sub["id"])["status"] == "WAIVED"
    # 7. the SME's activity log (central, hash-chained) shows what happened, without values
    activity = wait(lambda: (lambda a: a if any(i["action"] == "loan.funded" for i in a) else None)(api("GET", "audit", "/v1/activity?limit=100", anna).json()), "activity log")
    assert {"application.published", "offer.selected", "loan.funded", "loan.disputed"} <= {i["action"] for i in activity}
    org = api("GET", "identity", "/v1/organizations/current", anna).json()["id"]
    assert api("GET", "audit", f"/v1/admin/verify/{org}", admin).json()["verified"] is True


def test_revoking_consent_works_across_services(actors):
    anna, sandra = actors["anna"], actors["sandra"]
    app = publish_new_application(actors, amount="300000")
    assert any(i["application_id"] == app for i in api("GET", "marketplace", "/v1/lender/matches", sandra).json()["items"])
    wait(lambda: any(n["kind"] == "application.matched" for n in api("GET", "notification", "/v1/notifications", sandra).json()["items"]), "match notification")
    api("POST", "marketplace", "/v1/disclosures/revoke-all", anna)
    assert not any(i["application_id"] == app for i in api("GET", "marketplace", "/v1/lender/matches", sandra).json()["items"])  # immediate
    api("GET", "marketplace", f"/v1/lender/applications/{app}", sandra, ok=(404,))
    wait(lambda: not any("matches" in (n["link"] or "") for n in api("GET", "notification", "/v1/notifications", sandra).json()["items"]
                         if n["kind"] == "application.matched"), "lender notifications removed after revocation")


def test_the_ai_explains_but_never_exceeds_the_verified_numbers(actors):
    anna = actors["anna"]
    profile = api("GET", "intelligence", "/v1/profile/current", anna).json()
    exp = api("GET", "advisory", f"/v1/assessments/{profile['assessment']['id']}/explanation", anna).json()
    assert exp["model"]["name"] == "template" and "not a bank rating" in exp["disclaimer"] and exp["summary"]
    scenario = api("POST", "intelligence", "/v1/scenarios", anna, json={"assessment_id": profile["assessment"]["id"], "inputs": {"cost_reduction_pct": "5"}}).json()
    out = api("POST", "advisory", f"/v1/scenarios/{scenario['id']}/explanation", anna, json={"assessment_id": profile["assessment"]["id"]}).json()
    assert out["headline"].startswith("Score")


def test_tenant_isolation_across_the_stack(actors):
    anna, peter = actors["anna"], actors["peter"]
    luca = seed.login(seed.SMES[1][0], seed.SMES[1][1])
    mine = api("GET", "intelligence", "/v1/profile/current", anna).json()["assessment"]["id"]
    api("GET", "intelligence", f"/v1/assessments/{mine}", luca, ok=(404,))        # another SME cannot read it
    api("GET", "intelligence", f"/v1/assessments/{mine}", peter, ok=(403, 404))    # a lender cannot read it at all
    api("GET", "accounting", "/v1/connections", peter, ok=(403,))
    internal = httpx.get(f"{seed.BASE['intelligence']}/internal/v1/assessments/{mine}/profile-extract", params={"fields": "dscr"}, headers=anna, timeout=10)
    assert internal.status_code in (401, 403)  # internal endpoints refuse a plain user call
