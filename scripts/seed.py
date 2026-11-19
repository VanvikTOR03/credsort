#!/usr/bin/env python
"""Seeds demo organizations through the real APIs (idempotent). Everything is synthetic and clearly labelled as demo data.

Run automatically by scripts/dev_up.py. Every demo user can sign in through the web app's dev login.
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

import httpx
import jwt
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libs" / "credsort-common"))

from credsort_common.config import PORTS  # noqa: E402
from credsort_common.db import Database  # noqa: E402
from credsort_common.migrate import service_urls  # noqa: E402

SECRET = os.environ.get("DEV_USER_TOKEN_SECRET", "dev-only-user-secret-change-me-0123456789")
BASE = {s: f"http://127.0.0.1:{p}" for s, p in PORTS.items()}

PLATFORM = ("ops@credsort.demo", "CredSort Operations")
SMES = [
    ("anna.keller@muster-maschinenbau.demo", "Anna Keller", dict(type="SME", legal_name="Muster Maschinenbau AG", uid="CHE-114.236.581", legal_form="AG", industry="manufacturing", employees=48), "muster"),
    ("luca.bernasconi@alpina-gastro.demo", "Luca Bernasconi", dict(type="SME", legal_name="Alpina Gastro GmbH", uid="CHE-229.318.704", legal_form="GmbH", industry="hospitality", employees=22), "alpina"),
    ("mia.stalder@pixelwerk.demo", "Mia Stalder", dict(type="SME", legal_name="Pixelwerk Studio GmbH", uid="CHE-347.862.015", legal_form="GmbH", industry="software", employees=12), "pixelwerk"),
]
LENDERS = [
    ("sandra.huber@regionalbank-zuerich.demo", "Sandra Huber", "Regionalbank Zürich",
     {"amount_min": "100000", "amount_max": "1000000", "min_assessment_category": "C", "weights": {"assessment_score": 4, "equity_ratio": 3, "ebitda_margin": 3}}),
    ("peter.imhof@kantonalbank-bern.demo", "Peter Imhof", "Kantonalbank Bern",
     {"industries": ["manufacturing", "software"], "amount_min": "200000", "amount_max": "2000000", "min_assessment_category": "B", "min": {"equity_ratio": "0.25"},
      "max": {"debt_to_ebitda": "4"}, "weights": {"equity_ratio": 5, "debt_to_ebitda": 3}}),
    ("dana.vogel@helvetia-debt.demo", "Dana Vogel", "Helvetia Debt Partners",
     {"amount_min": "100000", "min_assessment_category": "C", "min": {"ebitda_margin": "0.05"}, "weights": {"revenue_growth": 5, "ebitda_margin": 4}}),
]
FIDUCIARY = ("marco.rossi@treuhand-rossi.demo", "Marco Rossi", "Treuhand Rossi AG")


def user_token(email: str, name: str) -> str:
    now = int(time.time())
    return jwt.encode({"sub": f"dev:{email}", "email": email, "name": name, "aud": "credsort-identity-dev", "iat": now, "exp": now + 3600}, SECRET, algorithm="HS256")


def call(method: str, service: str, path: str, ok=(200, 201, 202, 204), **kw) -> httpx.Response:
    r = httpx.request(method, BASE[service] + path, timeout=30.0, **kw)
    if r.status_code not in ok:
        raise SystemExit(f"{method} {service}{path} -> {r.status_code}: {r.text[:300]}")
    return r


def login(email: str, name: str, org_id: str | None = None) -> dict:
    r = call("POST", "identity", "/v1/context-tokens", json={"org_id": org_id}, headers={"Authorization": f"Bearer {user_token(email, name)}"}, ok=(200, 404))
    return {"Authorization": f"Bearer {r.json()['token']}"} if r.status_code == 200 else {}


def has_account(email: str, name: str) -> bool:
    r = call("GET", "identity", "/v1/me", headers={"Authorization": f"Bearer {user_token(email, name)}"})
    return bool(r.json()["memberships"])


def onboard(email: str, name: str, body: dict) -> None:
    if not has_account(email, name):
        call("POST", "identity", "/v1/organizations", json=body, headers={"Authorization": f"Bearer {user_token(email, name)}"})
        print(f"  created {body['legal_name']}")


def wait(fn, what: str, timeout: float = 90.0):
    end = time.time() + timeout
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.5)
    raise SystemExit(f"timed out waiting for {what}")


def seed_platform() -> None:
    url, _ = service_urls(os.environ["DEV_SUPERUSER_URL"], "identity")
    db = Database(url, "identity")
    with db.system() as s:
        if s.execute(text("select 1 from organizations where type = 'PLATFORM'")).first():
            return
        org, usr = uuid.uuid4(), uuid.uuid4()
        s.execute(text("insert into organizations(id, type, legal_name, kyb_status, referral_code) values (:i, 'PLATFORM', 'CredSort', 'VERIFIED', 'CS-PLATFM')"), {"i": org})
        s.execute(text("insert into users(id, email, display_name) values (:i, :e, :n)"), {"i": usr, "e": PLATFORM[0], "n": PLATFORM[1]})
        s.execute(text("insert into memberships(id, user_id, org_id, role) values (:i, :u, :o, 'PLATFORM_ADMIN')"), {"i": uuid.uuid4(), "u": usr, "o": org})
    print("  created platform operator account")


def main() -> None:
    print("seeding demo data (synthetic)")
    seed_platform()
    admin = login(*PLATFORM)
    for email, name, body, _ in SMES:
        onboard(email, name, body)
    for email, name, org, _ in LENDERS:
        onboard(email, name, dict(type="LENDER", legal_name=org))
    onboard(FIDUCIARY[0], FIDUCIARY[1], dict(type="FIDUCIARY", legal_name=FIDUCIARY[2]))
    for o in call("GET", "identity", "/v1/admin/organizations?kyb_status=PENDING", headers=admin).json():
        call("POST", "identity", f"/v1/admin/organizations/{o['id']}/verify", headers=admin)
        print(f"  verified {o['legal_name']}")

    if not call("GET", "billing", "/v1/admin/price-books", headers=admin).json():
        # Prices are not decided yet (ADR-0013). A clearly labelled DEMO price book lets the whole flow be shown; operators replace it.
        rule = lambda code, payer, pct, lo, hi: {"code": code, "payer": payer, "trigger": "LOAN_FUNDED", "calculator": "PERCENT_OF_PRINCIPAL", "percent": pct, "min_amount": lo, "cap_amount": hi}
        book = call("POST", "billing", "/v1/admin/price-books", headers=admin, json={"placeholder": True, "rules": [rule("SME_SUCCESS", "SME", "1.0", "1000", "8000"), rule("LENDER_SUCCESS", "LENDER", "0.75", "2000", "7500")]}).json()
        call("POST", "billing", f"/v1/admin/price-books/{book['id']}/activate", headers=admin, json={})
        print("  activated a DEMO price book (placeholder prices, not final)")

    profiles = {}
    for email, name, body, dataset in SMES:
        h = login(email, name)
        if not call("GET", "accounting", "/v1/connections", headers=h).json():
            cid = call("POST", "accounting", "/v1/connections", json={"source_type": "SYNTHETIC", "dataset": dataset}, headers=h).json()["id"]
            call("POST", "accounting", "/v1/import-jobs", json={"connection_id": cid}, headers=h)
            print(f"  importing {body['legal_name']}")
        profiles[email] = wait(lambda h=h: (lambda r: r.json() if r.status_code == 200 else None)(call("GET", "intelligence", "/v1/profile/current", headers=h, ok=(200, 404))),
                               f"profile of {body['legal_name']}")
        a = profiles[email]["assessment"]
        print(f"  {body['legal_name']}: category {a['category']} ({a['label']}), score {a['score']}, confidence {a['confidence']['band']}")

    for email, name, org, criteria in LENDERS:
        h = login(email, name)
        if call("GET", "marketplace", "/v1/lender/criteria", headers=h).json()["version"] == 0:
            call("PUT", "marketplace", "/v1/lender/criteria", json={"criteria": criteria}, headers=h)

    muster = SMES[0]
    h = login(muster[0], muster[1])
    if not call("GET", "marketplace", "/v1/applications", headers=h).json():
        aid = profiles[muster[0]]["assessment"]["id"]
        app = call("POST", "marketplace", "/v1/applications", json={"amount": "600000", "term_months": 60, "purpose": "Expansion of the production line", "assessment_id": aid}, headers=h).json()["id"]
        fields = ["requested_amount", "term_months", "industry", "employees_band", "assessment_category", "confidence_band", "revenue_band", "equity_ratio", "ebitda_margin", "debt_to_ebitda", "dscr"]
        call("POST", "marketplace", f"/v1/applications/{app}/publication", json={"fields": fields}, headers=h)
        print("  published a demo application for Muster Maschinenbau AG")
    pix = SMES[2]
    hp = login(pix[0], pix[1])
    if not call("GET", "marketplace", "/v1/applications", headers=hp).json():
        call("POST", "marketplace", "/v1/applications", json={"amount": "150000", "term_months": 36, "purpose": "Hire two developers", "assessment_id": profiles[pix[0]]["assessment"]["id"]}, headers=hp)
        print("  drafted an application for Pixelwerk Studio GmbH")
    alp = SMES[1]
    ha = login(alp[0], alp[1])
    fid_h = login(FIDUCIARY[0], FIDUCIARY[1])
    code = call("GET", "identity", "/v1/organizations/current", headers=fid_h).json()["referral_code"]
    if not call("GET", "identity", "/v1/delegations", headers=ha).json():
        call("POST", "identity", "/v1/delegations", json={"referral_code": code, "scopes": ["VIEW_PROFILE", "PREPARE_APPLICATION"]}, headers=ha)
        print("  Alpina Gastro shared access with Treuhand Rossi AG")
    print("demo accounts (sign in with the dev login):")
    for email, name, body, _ in SMES:
        print(f"  SME      {email}")
    for email, name, org, _ in LENDERS:
        print(f"  Lender   {email}")
    print(f"  Fiduciary {FIDUCIARY[0]}\n  Operator {PLATFORM[0]}")


if __name__ == "__main__":
    main()
