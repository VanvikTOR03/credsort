import datetime as dt
import json
import uuid
from decimal import Decimal

import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from conftest import LENDER_FEE, SME_FEE
from credsort_common.background import process_event
from credsort_common.security import JwksCache, RS256Verifier
from credsort_common.testing import service_headers

from app.consumers import consumers
from app.service import QUOTE_AUD, QUOTE_ISS


def consumer(name):
    return next(c for c in consumers() if c.name == name)


def funded(org, lender, offer, quote_ids, application=None):
    return {"id": str(uuid.uuid4()), "type": "credsort.marketplace.loan.funded.v1", "credsortorgid": str(org),
            "data": {"offer_id": str(offer), "application_id": str(application or uuid.uuid4()), "sme_org_id": str(org), "lender_org_id": str(lender),
                     "quote_ids": [str(q) for q in quote_ids]}}


def charges(env, org):
    with env.db.system() as s:
        return s.execute(text("select quote_id, amount, status, price_book_version from fee_charges where org_id = :o order by created_at"), {"o": org}).all()


# ---- quotes -------------------------------------------------------------------------------------
def test_unpriced_quote_when_no_price_book_is_active(env):
    q = env.quote(uuid.uuid4())
    assert q["pricing"] == "UNPRICED" and q["amount"] == "0" and q["price_book_version"] is None


def test_quote_is_signed_exact_and_bound_to_its_subject(env):
    env.new_book([SME_FEE])
    org, offer = uuid.uuid4(), uuid.uuid4()
    q = env.quote(org, subject=offer, basis="500000")
    assert q["pricing"] == "PRICED" and Decimal(q["amount"]) == Decimal("5000.00")
    verifier = RS256Verifier(JwksCache.static(env.keystore), audience=QUOTE_AUD, issuer=QUOTE_ISS)
    claims = verifier.verify(q["token"])
    assert claims["sub"] == str(offer) and claims["payer"] == str(org) and claims["amount"] == "5000.0000" and claims["qid"] == str(q["quote_id"])
    forged = jwt.encode({**claims, "amount": "1.00"}, "x" * 40, algorithm="HS256")
    from credsort_common.errors import Unauthorized
    with pytest.raises(Unauthorized):
        verifier.verify(forged)
    assert env.client.get("/.well-known/jwks.json").json()["keys"][0]["kid"] == env.keystore.kid


def test_quote_endpoint_is_only_for_the_marketplace(env):
    body = {"action": "LOAN_FUNDED", "subject_id": str(uuid.uuid4()), "payer_org_id": str(uuid.uuid4()), "payer_type": "SME", "basis": "1000"}
    assert env.client.post("/internal/v1/quotes", json=body, headers=env.tokens.headers()).status_code == 401
    assert env.client.post("/internal/v1/quotes", json=body, headers=service_headers("advisory", "billing")).status_code == 403
    assert env.client.post("/internal/v1/quotes", json={**body, "basis": "-5"}, headers=env.svc).status_code == 422
    assert env.client.post("/internal/v1/quotes", json={**body, "basis": 1000.5}, headers=env.svc).status_code == 422  # floats are refused


# ---- price books: a price change is a new version, never an edit ---------------------------------
def test_changing_a_price_is_a_new_version_and_old_quotes_keep_their_amount(env):
    first = env.new_book([SME_FEE])
    org, offer = uuid.uuid4(), uuid.uuid4()
    q_old = env.quote(org, subject=offer)  # quoted under version N
    env.new_book([{**SME_FEE, "percent": "2.0", "cap_amount": "20000"}])  # new version, zero code change (FF-E1)
    q_new = env.quote(org, subject=uuid.uuid4())
    assert Decimal(q_old["amount"]) == Decimal("5000.00") and Decimal(q_new["amount"]) == Decimal("10000.00") and q_new["price_book_version"] == q_old["price_book_version"] + 1
    process_event(env.db, consumer("billing-funded"), funded(org, uuid.uuid4(), offer, [q_old["quote_id"]]))
    (c,) = charges(env, org)
    assert c.amount == Decimal("5000.0000") and c.price_book_version == q_old["price_book_version"]  # charged exactly as quoted


def test_active_price_book_rules_are_immutable_in_the_database(env):
    book = env.new_book([SME_FEE])
    with pytest.raises(DBAPIError):
        with env.db.session(None, "PLATFORM") as s:
            s.execute(text("update fee_rules set percent = 99 where price_book_id = :b"), {"b": book["id"]})
    with pytest.raises(DBAPIError):
        with env.db.session(None, "PLATFORM") as s:
            s.execute(text("delete from fee_rules where price_book_id = :b"), {"b": book["id"]})


def test_only_one_active_book_and_admin_only_endpoints(env):
    env.new_book([SME_FEE])
    env.new_book([LENDER_FEE])
    active = [b for b in env.client.get("/v1/admin/price-books", headers=env.admin).json() if b["status"] == "ACTIVE"]
    assert len(active) == 1 and active[0]["rules"][0]["code"] == "LENDER_SUCCESS"
    sme = env.tokens.headers()
    assert env.client.get("/v1/admin/price-books", headers=sme).status_code == 403
    assert env.client.post("/v1/admin/price-books", json={"rules": [SME_FEE]}, headers=sme).status_code == 403
    pub = env.client.get("/v1/pricing", headers=sme).json()
    assert pub["status"] == "ACTIVE" and pub["placeholder"] is True and pub["rules"][0]["code"] == "LENDER_SUCCESS"


def test_pricing_says_so_when_nothing_is_decided_yet(env):
    assert env.client.get("/v1/pricing", headers=env.tokens.headers()).json() == {"status": "NONE", "placeholder": False, "rules": []}


# ---- charges --------------------------------------------------------------------------------------
def test_charge_is_recorded_only_when_the_loan_is_funded_and_equals_the_quote(env):
    env.new_book([SME_FEE, LENDER_FEE])
    sme, lender, offer = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    qs, ql = env.quote(sme, "SME", offer), env.quote(lender, "LENDER", offer)
    assert charges(env, sme) == [] and charges(env, lender) == []  # selecting an offer costs nothing
    process_event(env.db, consumer("billing-funded"), funded(sme, lender, offer, [qs["quote_id"], ql["quote_id"]]))
    (cs,), (cl,) = charges(env, sme), charges(env, lender)
    assert (cs.amount, cs.status) == (Decimal(qs["amount"]), "RECORDED") and (cl.amount, cl.status) == (Decimal(ql["amount"]), "RECORDED")
    with env.db.system() as s:
        ev = s.execute(text("select payload from outbox where event_type like '%charge.recorded%' and org_id = :o"), {"o": sme}).scalar()
        payable = s.execute(text("select payable_after from fee_charges where org_id = :o"), {"o": sme}).scalar()
    assert set(ev["data"]) == {"charge_id", "org_id", "quote_id"}  # thin: no amounts in events
    assert payable > dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=13)  # payable only after the 14-day dispute window


def test_duplicate_delivery_and_double_events_never_double_charge(env):
    env.new_book([SME_FEE])
    sme, lender, offer = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    q = env.quote(sme, "SME", offer)
    ev = funded(sme, lender, offer, [q["quote_id"]])
    assert process_event(env.db, consumer("billing-funded"), ev) is True
    assert process_event(env.db, consumer("billing-funded"), ev) is False  # RabbitMQ delivered the same message twice: inbox
    process_event(env.db, consumer("billing-funded"), funded(sme, lender, offer, [q["quote_id"]]))  # a different event for the same quote: unique per quote
    assert len(charges(env, sme)) == 1


def test_unknown_or_mismatched_quotes_are_held_never_guessed(env):
    env.new_book([SME_FEE])
    sme, lender = uuid.uuid4(), uuid.uuid4()
    process_event(env.db, consumer("billing-funded"), funded(sme, lender, uuid.uuid4(), [uuid.uuid4()]))
    q = env.quote(sme, "SME", subject=uuid.uuid4())
    process_event(env.db, consumer("billing-funded"), funded(sme, lender, uuid.uuid4(), [q["quote_id"]]))  # quote belongs to another offer
    with env.db.system() as s:
        reasons = sorted(r[0] for r in s.execute(text("select reason_code from held_events")).all() if r)
        n = s.execute(text("select count(*) from outbox where event_type like '%charge.held%'")).scalar()
    assert {"UNKNOWN_QUOTE", "SUBJECT_MISMATCH"} <= set(reasons) and n >= 2 and charges(env, sme) == []


def test_unpriced_funding_creates_a_no_fee_record(env):
    sme, offer = uuid.uuid4(), uuid.uuid4()
    q = env.quote(sme, "SME", offer)
    process_event(env.db, consumer("billing-funded"), funded(sme, uuid.uuid4(), offer, [q["quote_id"]]))
    assert charges(env, sme)[0].status == "NO_FEE"


def test_dispute_holds_the_fee_and_admin_can_release_or_waive(env):
    env.new_book([SME_FEE])
    sme, lender, offer = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    q = env.quote(sme, "SME", offer)
    process_event(env.db, consumer("billing-funded"), funded(sme, lender, offer, [q["quote_id"]]))
    dispute = {**funded(sme, lender, offer, [q["quote_id"]]), "type": "credsort.marketplace.loan.disputed.v1"}
    process_event(env.db, consumer("billing-disputed"), dispute)
    assert charges(env, sme)[0].status == "HELD"
    charge_id = env.client.get("/v1/admin/charges?status=HELD", headers=env.admin).json()[0]["id"]
    assert env.client.post(f"/v1/admin/charges/{charge_id}/waive", headers=env.admin).json()["status"] == "WAIVED"
    assert env.client.post(f"/v1/admin/charges/{charge_id}/waive", headers=env.admin).status_code == 409  # resolved once


def test_cancelled_loan_drops_the_fee(env):
    env.new_book([SME_FEE])
    sme, offer = uuid.uuid4(), uuid.uuid4()
    q = env.quote(sme, "SME", offer)
    process_event(env.db, consumer("billing-funded"), funded(sme, uuid.uuid4(), offer, [q["quote_id"]]))
    cancel = {**funded(sme, uuid.uuid4(), offer, [q["quote_id"]]), "type": "credsort.marketplace.loan.cancelled.v1"}
    process_event(env.db, consumer("billing-cancelled"), cancel)
    assert charges(env, sme)[0].status == "CANCELLED"


def test_referral_share_goes_to_the_fiduciary_who_referred_the_sme(env):
    env.new_book([SME_FEE])
    sme, fid, lender, offer = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    created = {"id": str(uuid.uuid4()), "type": "credsort.identity.organization.created.v1", "credsortorgid": str(sme),
               "data": {"org_id": str(sme), "org_type": "SME", "referred_by_org_id": str(fid)}}
    process_event(env.db, consumer("billing-referrals"), created)
    q = env.quote(sme, "SME", offer)
    process_event(env.db, consumer("billing-funded"), funded(sme, lender, offer, [q["quote_id"]]))
    with env.db.system() as s:
        share = s.execute(text("select fiduciary_org_id, percent, amount from referral_shares where org_id = :o"), {"o": sme}).first()
    assert share.fiduciary_org_id == fid and share.percent == Decimal("20.00") and share.amount == Decimal(q["amount"]) * Decimal("0.2")


# ---- access ---------------------------------------------------------------------------------------
def test_charges_are_private_to_the_payer(env):
    env.new_book([SME_FEE])
    sme, other, offer = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    q = env.quote(sme, "SME", offer)
    process_event(env.db, consumer("billing-funded"), funded(sme, uuid.uuid4(), offer, [q["quote_id"]]))
    mine = env.client.get("/v1/charges", headers=env.tokens.headers(org_id=sme)).json()
    theirs = env.client.get("/v1/charges", headers=env.tokens.headers(org_id=other)).json()
    assert len(mine) == 1 and isinstance(mine[0]["amount"], str) and theirs == []


def test_entitlements_default_to_everything_and_follow_overrides(env):
    org = uuid.uuid4()
    h = {**env.tokens.headers(org_id=org), **service_headers("intelligence", "billing")}
    assert set(env.client.get(f"/internal/v1/organizations/{org}/entitlements", headers=h).json()["entitlements"]) == {"PROFILE", "APPLY", "ADVISOR", "WHAT_IF"}
    assert env.client.get(f"/internal/v1/organizations/{uuid.uuid4()}/entitlements", headers=h).status_code == 404  # not your organization
    assert env.client.post("/v1/admin/entitlements", json={"org_id": str(org), "entitlements": ["PROFILE", "NOPE"]}, headers=env.admin).status_code == 422
    assert env.client.post("/v1/admin/entitlements", json={"org_id": str(org), "entitlements": ["PROFILE"]}, headers=env.admin).status_code == 200
    assert env.client.get(f"/internal/v1/organizations/{org}/entitlements", headers=h).json()["entitlements"] == ["PROFILE"]
    with env.db.system() as s:
        assert s.execute(text("select count(*) from outbox where event_type like '%entitlements.changed%' and org_id = :o"), {"o": org}).scalar() == 1


def test_every_tenant_table_has_row_level_security(env):
    with env.db.system() as s:
        rows = s.execute(text("select relname, relrowsecurity and relforcerowsecurity as ok from pg_class c join pg_namespace n on n.oid = c.relnamespace "
                              "where n.nspname = 'public' and c.relkind = 'r'")).all()
    assert [r.relname for r in rows if not r.ok and r.relname not in {"schema_migrations", "inbox", "denylist", "tombstones"}] == []
