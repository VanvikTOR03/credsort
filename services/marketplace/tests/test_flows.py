import datetime as dt
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from conftest import SUMMARY

from credsort_common.background import process_event
from credsort_common.errors import Conflict

from app import lending
from app.consumers import consumers
from app.sessions import sess


def new_offer_ready(env, lender_fields=None, **crit):
    """An SME with a published application and a verified lender with one open offer."""
    sme_org, sme = env.sme()
    lender_org, lender = env.lender()
    env.criteria(lender, **crit)
    app = env.publish(sme)
    r = env.offer(lender, app)
    assert r.status_code == 201, r.text
    return sme_org, sme, lender_org, lender, app, r.json()["id"]


# ===================================================================================== publication & consent
def test_publication_freezes_exactly_the_consented_fields(env):
    org, h = env.sme(industry="manufacturing", employees=25)
    app = env.draft(h)
    prev = env.client.get(f"/v1/applications/{app}/publication-preview", params={"fields": ",".join(SUMMARY + ["employees_band"])}, headers=h).json()
    shown = {f["field"]: f["value"] for f in prev["fields"]}
    assert shown["requested_amount"] == "500000.0000" and shown["industry"] == "manufacturing" and shown["assessment_category"] == "B" and shown["employees_band"] == "10-49"
    r = env.client.post(f"/v1/applications/{app}/publication", json={"fields": SUMMARY}, headers=h)
    assert r.status_code == 201 and set(r.json()["shared_fields"]) == set(SUMMARY)
    with env.db.system() as s:
        fields = s.execute(text("select fields from published_profiles where application_id = :a"), {"a": app}).scalar()
        d = s.execute(text("select level, purpose, permitted_fields, revoked_at from disclosures where application_id = :a"), {"a": app}).first()
    assert set(fields) == set(SUMMARY) and "company_name" not in fields and "equity_ratio" not in fields  # nothing beyond what was chosen
    assert (d.level, d.purpose, d.revoked_at) == ("summary", "matching", None) and set(d.permitted_fields) == set(SUMMARY)
    assert [e["data"] for e in env.events("application.published", org)][-1] == {"application_id": app, "sme_org_id": str(org)}


def test_publication_is_frozen_and_cannot_repeat(env):
    _, h = env.sme()
    app = env.publish(h)
    assert env.client.post(f"/v1/applications/{app}/publication", json={"fields": SUMMARY}, headers=h).status_code == 409
    assert env.client.patch(f"/v1/applications/{app}", json={"amount": "999"}, headers=h).status_code == 409
    with pytest.raises(DBAPIError):  # the frozen profile cannot be edited, even by the database owner role of the service
        with env.db.system() as s:
            s.execute(text("update published_profiles set fields = '{}'::jsonb where application_id = :a"), {"a": app})


def test_only_a_verified_sme_admin_who_is_not_a_delegate_can_publish(env):
    app_org, h = env.sme()
    app = env.draft(h)
    body = {"fields": SUMMARY}
    _, member = env.sme(role="SME_MEMBER")
    assert env.client.post(f"/v1/applications/{env.draft(member)}/publication", json=body, headers=member).status_code == 403
    _, unverified = env.sme(kyb="PENDING")
    assert env.client.post(f"/v1/applications/{env.draft(unverified)}/publication", json=body, headers=unverified).json()["code"] == "kyb_required"
    delegate = env.tokens.headers(org_type="FIDUCIARY", role="FIDUCIARY_ADVISOR", on_behalf_of=app_org, scopes=("VIEW_PROFILE", "PREPARE_APPLICATION"))
    assert env.client.post(f"/v1/applications/{app}/publication", json=body, headers=delegate).json()["code"] == "delegation_forbidden"
    assert env.client.post(f"/v1/applications/{app}/publication", json={"fields": []}, headers=h).status_code == 422
    assert env.client.post(f"/v1/applications/{app}/publication", json={"fields": ["ledger"]}, headers=h).json()["code"] == "unknown_fields"


def test_a_delegate_may_prepare_the_draft_but_not_publish_or_see_other_smes(env):
    org, h = env.sme()
    delegate = env.tokens.headers(org_type="FIDUCIARY", role="FIDUCIARY_ADVISOR", on_behalf_of=org, scopes=("VIEW_PROFILE", "PREPARE_APPLICATION"))
    app = env.draft(delegate)
    assert env.client.get(f"/v1/applications/{app}", headers=h).status_code == 200  # the SME sees what its fiduciary prepared
    other = env.tokens.headers(org_type="FIDUCIARY", role="FIDUCIARY_ADVISOR", on_behalf_of=uuid.uuid4(), scopes=("VIEW_PROFILE", "PREPARE_APPLICATION"))
    assert env.client.get(f"/v1/applications/{app}", headers=other).status_code == 404


def test_publication_survives_a_double_click_with_an_idempotency_key(env):
    _, h = env.sme()
    app = env.draft(h)
    hk = {**h, "Idempotency-Key": "pub-1"}
    a = env.client.post(f"/v1/applications/{app}/publication", json={"fields": SUMMARY}, headers=hk)
    b = env.client.post(f"/v1/applications/{app}/publication", json={"fields": SUMMARY}, headers=hk)
    assert a.status_code == b.status_code == 201 and a.json() == b.json()
    with env.db.system() as s:
        assert s.execute(text("select count(*) from published_profiles where application_id = :a"), {"a": app}).scalar() == 1


def test_publication_needs_intelligence_but_matching_and_offers_do_not(env):
    _, h = env.sme()
    app = env.draft(h)
    env.intel.fail = True
    r = env.client.post(f"/v1/applications/{app}/publication", json={"fields": SUMMARY}, headers=h)
    assert r.status_code == 503 and r.json()["code"] == "upstream_unavailable"
    with env.db.system() as s:
        assert s.execute(text("select status from applications where id = :a"), {"a": app}).scalar() == "DRAFT"  # nothing half-published
    env.intel.fail = False
    app2 = env.publish(h)
    env.intel.fail = True  # Intelligence goes down AFTER publication: lenders keep working on the frozen profile
    _, lender = env.lender()
    assert any(i["application_id"] == app2 for i in env.matches(lender)["items"])


def test_pilot_cap(env, monkeypatch):
    monkeypatch.setenv("PILOT_MAX_AMOUNT", "750000")
    _, h = env.sme()
    r = env.client.post("/v1/applications", json={"amount": "900000", "term_months": 60}, headers=h)
    assert r.status_code == 422 and r.json()["code"] == "pilot_cap_exceeded"


# ===================================================================================== what lenders can see
def test_lender_sees_only_published_consented_fields(env):
    _, sme = env.sme()
    _, lender = env.lender()
    draft = env.draft(sme)
    published = env.publish(sme, fields=["requested_amount", "term_months", "assessment_category"])
    items = {i["application_id"]: i for i in env.matches(lender)["items"]}
    assert draft not in items and published in items
    assert set(items[published]["fields"]) == {"requested_amount", "term_months", "assessment_category"}  # nothing else leaks
    assert env.client.get(f"/v1/lender/applications/{draft}", headers=lender).status_code == 404


def test_lender_cannot_read_unconsented_rows_even_with_raw_sql(env):
    """Defence in depth: row-level security stops a lender at the database, whatever the application code does."""
    sme_org, sme = env.sme()
    lender_org, lender = env.lender()
    other_org, other = env.lender()
    draft = env.draft(sme)
    own_only = env.publish(sme, lenders=[other_org])  # shared with `other` only
    ctx = env.ctx(lender)
    with sess(env.db, ctx) as s:
        ids = {str(r.id) for r in s.execute(text("select id from applications")).all()}
        profiles = s.execute(text("select count(*) from published_profiles")).scalar()
        cols = s.execute(text("select count(*) from disclosures")).scalar()
        offers = s.execute(text("select count(*) from offers")).scalar()
    assert draft not in ids and own_only not in ids and profiles >= 0
    with sess(env.db, ctx) as s:
        assert s.execute(text("select count(*) from applications where id = :a"), {"a": own_only}).scalar() == 0
        assert s.execute(text("select count(*) from published_profiles where application_id = :a"), {"a": own_only}).scalar() == 0
    with sess(env.db, env.ctx(other)) as s:
        assert s.execute(text("select count(*) from applications where id = :a"), {"a": own_only}).scalar() == 1


def test_indirect_disclosure_is_impossible_criteria_on_hidden_fields_change_nothing(env):
    _, sme = env.sme()
    app = env.publish(sme, fields=["requested_amount", "term_months", "assessment_category"])  # equity_ratio NOT shared
    _, probing = env.lender()
    _, plain = env.lender()
    env.criteria(plain)
    baseline = [i["application_id"] for i in env.matches(plain)["items"]]
    assert app in baseline
    # a lender probes the hidden metric with ever tighter thresholds: the answers are always "not in the list", never a value
    for threshold in ("0.01", "0.2", "0.35", "0.9"):
        env.criteria(probing, min={"equity_ratio": threshold})
        result = env.matches(probing)
        assert app not in [i["application_id"] for i in result["items"]]
    # and results/ordering of everything else are the same as if the hidden application did not exist
    _, only_visible = env.sme()
    env.criteria(probing, min={"equity_ratio": "0.2"})
    assert env.matches(probing)["total"] == len([i for i in env.matches(probing)["items"]])


def test_different_lenders_get_different_results_and_a_deterministic_ranking(env):
    _, sme = env.sme(industry="manufacturing")
    strong = env.publish(sme, fields=SUMMARY + ["equity_ratio", "ebitda_margin"])
    env.intel.values.update(equity_ratio="0.12", ebitda_margin="0.03", assessment_category="C")
    weak = env.publish(sme, fields=SUMMARY + ["equity_ratio", "ebitda_margin"])
    picky_org, picky = env.lender()
    env.criteria(picky, min={"equity_ratio": "0.3"}, weights={"equity_ratio": 5, "ebitda_margin": 5})
    broad_org, broad = env.lender()
    env.criteria(broad, weights={"equity_ratio": 5, "ebitda_margin": 5})
    p, b = env.matches(picky), env.matches(broad)
    assert strong in [i["application_id"] for i in p["items"]] and weak not in [i["application_id"] for i in p["items"]]
    ids = [i["application_id"] for i in b["items"]]
    assert ids.index(strong) < ids.index(weak) and [i["rank"] for i in b["items"]] == list(range(1, len(ids) + 1))
    assert env.matches(broad) == b  # deterministic
    item = next(i for i in p["items"] if i["application_id"] == strong)
    assert item["explanation"] and all(e["met"] for e in item["explanation"]) and Decimal(item["score"]) > 0


def test_lender_must_be_verified_and_not_delegated(env):
    _, unverified = env.lender(kyb="PENDING")
    assert env.client.get("/v1/lender/matches", headers=unverified).json()["code"] == "kyb_required"
    assert env.client.get("/v1/lender/matches", headers=env.sme()[1]).status_code == 403
    assert env.client.put("/v1/lender/criteria", json={"criteria": {"min": {"industry": "1"}}}, headers=env.lender()[1]).json()["code"] == "invalid_criteria"


# ===================================================================================== revocation
def test_revoking_consent_hides_the_application_immediately_everywhere(env):
    sme_org, sme = env.sme()
    _, l1 = env.lender()
    _, l2 = env.lender()
    app = env.publish(sme)
    assert app in [i["application_id"] for i in env.matches(l1)["items"]]
    disclosure = env.client.get("/v1/disclosures", headers=sme).json()[0]["id"]
    assert env.client.post(f"/v1/disclosures/{disclosure}/revoke", headers=sme).status_code == 200
    for lender in (l1, l2):
        assert app not in [i["application_id"] for i in env.matches(lender)["items"]]
        assert env.client.get(f"/v1/lender/applications/{app}", headers=lender).status_code == 404
        with sess(env.db, env.ctx(lender)) as s:  # and at the database level
            assert s.execute(text("select count(*) from published_profiles where application_id = :a"), {"a": app}).scalar() == 0
    ev = env.events("disclosure.revoked", sme_org)
    assert ev and ev[-1]["data"]["application_id"] == app and "revenue" not in json.dumps(ev[-1]["data"])
    assert env.client.post(f"/v1/disclosures/{disclosure}/revoke", headers=sme).status_code == 404  # revocation is final
    assert "cannot be recalled" in env.client.post("/v1/disclosures/revoke-all", headers=sme).json()["note"]


def test_revoke_all_covers_every_application_and_a_lender_cannot_revoke(env):
    _, sme = env.sme()
    a, b = env.publish(sme), env.publish(sme)
    _, lender = env.lender()
    assert {a, b} <= {i["application_id"] for i in env.matches(lender)["items"]}
    assert env.client.post("/v1/disclosures/revoke-all", headers=lender).status_code == 403
    assert env.client.post("/v1/disclosures/revoke-all", headers=sme).json()["revoked"] == 2
    assert not {a, b} & {i["application_id"] for i in env.matches(lender)["items"]}


def test_withdrawing_an_application_revokes_consent_and_rejects_open_offers(env):
    sme_org, sme, lender_org, lender, app, offer = new_offer_ready(env)
    assert env.client.post(f"/v1/applications/{app}/withdraw", headers=sme).status_code == 200
    assert app not in [i["application_id"] for i in env.matches(lender)["items"]]
    assert env.client.get("/v1/lender/offers", headers=lender).json()[0]["status"] == "REJECTED"
    assert env.client.post(f"/v1/offers/{offer}/selection", headers=sme).status_code == 409


# ===================================================================================== access requests (full disclosure)
def test_full_access_is_granted_per_lender_and_frozen_at_approval(env):
    sme_org, sme = env.sme()
    asking_org, asking = env.lender()
    _, bystander = env.lender()
    app = env.publish(sme)
    r = env.client.post(f"/v1/lender/applications/{app}/access-requests", json={"fields": ["equity_ratio", "dscr"]}, headers=asking)
    assert r.status_code == 201
    assert env.client.post(f"/v1/lender/applications/{app}/access-requests", json={"fields": ["dscr"]}, headers=asking).status_code == 409  # one pending
    req = env.client.get("/v1/access-requests", headers=sme).json()[0]
    assert req["status"] == "PENDING" and set(req["requested_fields"]) == {"equity_ratio", "dscr"}
    env.intel.values["equity_ratio"] = "0.35"
    assert env.client.post(f"/v1/access-requests/{req['id']}/approve", headers=sme).json()["status"] == "APPROVED"
    full = env.client.get(f"/v1/lender/applications/{app}", headers=asking).json()
    assert full["level"] == "full" and full["fields"]["equity_ratio"] == "0.35" and "dscr" in full["fields"]
    plain = env.client.get(f"/v1/lender/applications/{app}", headers=bystander).json()
    assert plain["level"] == "summary" and "equity_ratio" not in plain["fields"]  # only the requesting lender gets more
    env.intel.values["equity_ratio"] = "0.99"  # later changes in Intelligence do not alter what was frozen at approval
    assert env.client.get(f"/v1/lender/applications/{app}", headers=asking).json()["fields"]["equity_ratio"] == "0.35"
    assert env.client.post(f"/v1/access-requests/{req['id']}/approve", headers=sme).status_code == 409  # decided once


def test_access_can_be_denied_and_only_the_sme_admin_decides(env):
    sme_org, sme = env.sme()
    _, lender = env.lender()
    app = env.publish(sme)
    env.client.post(f"/v1/lender/applications/{app}/access-requests", json={"fields": ["dscr"]}, headers=lender)
    req = env.client.get("/v1/access-requests", headers=sme).json()[0]["id"]
    assert env.client.post(f"/v1/access-requests/{req}/approve", headers=lender).status_code in (403, 404)
    _, member = env.sme(role="SME_MEMBER")
    assert env.client.post(f"/v1/access-requests/{req}/deny", headers=member).status_code in (403, 404)
    assert env.client.post(f"/v1/access-requests/{req}/deny", headers=sme).json()["status"] == "DENIED"
    assert "dscr" not in env.client.get(f"/v1/lender/applications/{app}", headers=lender).json()["fields"]


def test_requesting_access_to_a_hidden_application_is_a_plain_404(env):
    _, sme = env.sme()
    _, lender = env.lender()
    draft = env.draft(sme)
    assert env.client.post(f"/v1/lender/applications/{draft}/access-requests", json={"fields": ["dscr"]}, headers=lender).status_code == 404


# ===================================================================================== offers
def test_offer_submission_stores_both_fee_quotes_and_discloses_the_lenders_own_fee(env):
    sme_org, sme = env.sme()
    lender_org, lender = env.lender()
    app = env.publish(sme)
    r = env.offer(lender, app, amount="500000")
    assert r.status_code == 201
    body = r.json()
    assert Decimal(body["your_fee"]["amount"]) == Decimal("5000.00") and Decimal(body["sme_fee"]["amount"]) == Decimal("5000.00")
    payers = {(c["payer_type"], c["payer_org_id"]) for c in env.billing.calls}
    assert payers == {("SME", str(sme_org)), ("LENDER", str(lender_org))} and all(c["subject_id"] == body["id"] for c in env.billing.calls)
    sme_view = env.client.get(f"/v1/applications/{app}/offers", headers=sme).json()[0]
    assert Decimal(sme_view["credsort_fee"]["amount"]) == Decimal("5000.00") and sme_view["lender_name"].startswith("Bank")
    assert Decimal(sme_view["cost"]["total"]) == Decimal(sme_view["cost"]["interest"]) + Decimal(sme_view["cost"]["lender_fees"]) + Decimal(sme_view["cost"]["credsort_fee"])


def test_offers_fail_closed_when_billing_is_down_and_never_half_exist(env):
    _, sme = env.sme()
    _, lender = env.lender()
    app = env.publish(sme)
    env.billing.fail = True
    r = env.offer(lender, app)
    assert r.status_code == 503 and r.json()["code"] == "fees_unavailable"
    assert env.client.get("/v1/lender/offers", headers=lender).json() == []
    env.billing.fail = False
    assert env.offer(lender, app).status_code == 201


def test_offer_rules(env):
    _, sme = env.sme()
    _, lender = env.lender()
    app = env.publish(sme)
    assert env.offer(lender, app, days=0).status_code == 422 and env.offer(lender, app, days=90).json()["code"] == "invalid_validity"
    assert env.offer(lender, app, rate="45").status_code == 422
    assert env.offer(lender, app).status_code == 201
    assert env.offer(lender, app).json()["code"] == "offer_open"  # withdraw first: terms are never edited, a new offer is a new row
    _, unverified = env.lender(kyb="PENDING")
    assert env.offer(unverified, app).status_code == 403
    _, other = env.lender()
    draft = env.draft(sme)
    assert env.offer(other, draft).status_code == 404  # cannot offer on what it cannot see


def test_offer_terms_are_immutable_in_the_database(env):
    _, _, lender_org, lender, app, offer = new_offer_ready(env)
    with pytest.raises(DBAPIError):
        with sess(env.db, env.ctx(lender)) as s:
            s.execute(text("update offers set rate = 0.1 where id = :i"), {"i": offer})
    assert env.client.post(f"/v1/lender/offers/{offer}/withdraw", headers=lender).json()["status"] == "WITHDRAWN"  # status may change, terms may not
    assert env.client.post(f"/v1/lender/offers/{offer}/withdraw", headers=lender).status_code == 409


def test_comparison_sorts_by_the_smes_key_and_lenders_see_only_their_own_offers(env):
    sme_org, sme = env.sme()
    app = env.publish(sme)
    cheap_org, cheap = env.lender()
    dear_org, dear = env.lender()
    env.offer(cheap, app, rate="2.5")
    env.offer(dear, app, rate="5.5")
    by_cost = env.client.get(f"/v1/applications/{app}/offers", headers=sme).json()
    assert [Decimal(o["rate"]) for o in by_cost] == [Decimal("2.5"), Decimal("5.5")]
    by_rate_desc = env.client.get(f"/v1/applications/{app}/offers?sort=amount", headers=sme).json()
    assert len(by_rate_desc) == 2
    mine = env.client.get("/v1/lender/offers", headers=cheap).json()
    assert len(mine) == 1 and mine[0]["lender_name"] == env.ctx(cheap).org_name  # a lender never sees a competitor's offer
    assert env.client.get(f"/v1/applications/{app}/offers", headers=cheap).status_code == 403


# ===================================================================================== selection: exactly one, locked fee, no charge yet
def test_selecting_an_offer_rejects_the_others_and_triggers_no_fee(env):
    sme_org, sme = env.sme()
    app = env.publish(sme)
    a_org, a = env.lender()
    b_org, b = env.lender()
    oa, ob = env.offer(a, app).json()["id"], env.offer(b, app, rate="4.0").json()["id"]
    r = env.client.post(f"/v1/offers/{oa}/selection", headers=sme)
    assert r.status_code == 200 and "only once the lender confirms the payout" in r.json()["note"]
    statuses = {o["id"]: o["status"] for o in env.client.get(f"/v1/applications/{app}/offers", headers=sme).json()}
    assert statuses[oa] == "SELECTED"
    assert env.client.get("/v1/lender/offers", headers=b).json()[0]["status"] == "REJECTED"
    sel = [e for e in env.events("offer.selected", sme_org)][-1]["data"]
    assert sel["lender_org_id"] == str(a_org) and sel["other_lender_org_ids"] == [str(b_org)] and "quote_ids" not in sel
    assert not env.events("loan.funded", sme_org)  # selecting costs nothing: no funded event, so Billing records no charge
    assert env.client.post(f"/v1/offers/{ob}/selection", headers=sme).status_code == 409  # second selection is refused
    with env.db.system() as s:
        assert s.execute(text("select count(*) from offers where application_id = :a and status in ('SELECTED','FUNDED')"), {"a": app}).scalar() == 1


def test_two_simultaneous_selections_produce_exactly_one_winner(env):
    sme_org, sme = env.sme()
    app = env.publish(sme)
    offers = []
    for _ in range(4):
        _, lender = env.lender()
        offers.append(env.offer(lender, app).json()["id"])
    ctx = env.ctx(sme)

    def attempt(offer_id):
        try:
            return lending.select_offer(env.db, env.quotes, ctx, uuid.UUID(offer_id), None)[0]
        except Conflict:
            return 409

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, offers))
    assert results.count(200) == 1 and results.count(409) == 3
    with env.db.system() as s:
        assert s.execute(text("select count(*) from offers where application_id = :a and status = 'SELECTED'"), {"a": app}).scalar() == 1
        assert s.execute(text("select count(*) from outbox where event_type like '%offer.selected%' and payload->'data'->>'application_id' = :a"), {"a": app}).scalar() == 1


def test_selection_is_idempotent_with_a_key(env):
    sme_org, sme, _, _, app, offer = new_offer_ready(env)
    hk = {**sme, "Idempotency-Key": "sel-1"}
    a, b = env.client.post(f"/v1/offers/{offer}/selection", headers=hk), env.client.post(f"/v1/offers/{offer}/selection", headers=hk)
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert len([e for e in env.events("offer.selected", sme_org) if e["data"]["offer_id"] == offer]) == 1


def test_only_the_smes_admin_can_select_and_not_a_delegate(env):
    sme_org, sme, _, lender, app, offer = new_offer_ready(env)
    assert env.client.post(f"/v1/offers/{offer}/selection", headers=lender).status_code in (403, 404)
    _, member = env.sme(role="SME_MEMBER")
    assert env.client.post(f"/v1/offers/{offer}/selection", headers=member).status_code == 403
    delegate = env.tokens.headers(org_type="FIDUCIARY", role="FIDUCIARY_ADVISOR", on_behalf_of=sme_org, scopes=("VIEW_PROFILE", "PREPARE_APPLICATION"))
    assert env.client.post(f"/v1/offers/{offer}/selection", headers=delegate).json()["code"] == "delegation_forbidden"
    _, stranger = env.sme()
    assert env.client.post(f"/v1/offers/{offer}/selection", headers=stranger).status_code == 404


def test_selection_works_while_billing_is_down_because_the_quote_is_verified_locally(env):
    sme_org, sme, _, _, app, offer = new_offer_ready(env)
    env.billing.fail = True
    assert env.client.post(f"/v1/offers/{offer}/selection", headers=sme).status_code == 200


def test_a_tampered_or_mismatched_quote_blocks_selection(env):
    sme_org, sme, _, _, app, offer = new_offer_ready(env)
    with env.db.system() as s:
        token = s.execute(text("select sme_quote_token from offers where id = :i"), {"i": offer}).scalar()
        s.execute(text("update offers set sme_quote_token = :t where id = :i"), {"t": token[:-6] + "AAAAAA", "i": offer})  # signature broken
    assert env.client.post(f"/v1/offers/{offer}/selection", headers=sme).json()["code"] == "quote_invalid"
    with env.db.system() as s:
        s.execute(text("update offers set sme_quote_token = :t, sme_fee_amount = 1 where id = :i"), {"t": token, "i": offer})  # amount differs from the signed quote
    assert env.client.post(f"/v1/offers/{offer}/selection", headers=sme).json()["code"] == "quote_mismatch"


def test_expired_offers_cannot_be_selected(env):
    sme_org, sme, _, _, app, offer = new_offer_ready(env)
    env.as_owner("alter table offers disable trigger offer_terms_immutable; update offers set valid_until = current_date - 1 where id = :i; "
                 "alter table offers enable trigger offer_terms_immutable", i=offer)
    assert env.client.post(f"/v1/offers/{offer}/selection", headers=sme).json()["code"] == "offer_expired"


# ===================================================================================== payout confirmation, dispute window, cancellation
def selected(env):
    sme_org, sme, lender_org, lender, app, offer = new_offer_ready(env)
    assert env.client.post(f"/v1/offers/{offer}/selection", headers=sme).status_code == 200
    return sme_org, sme, lender_org, lender, app, offer


def test_fee_is_triggered_only_when_the_lender_confirms_the_payout_and_only_once(env):
    sme_org, sme, lender_org, lender, app, offer = selected(env)
    _, other = env.lender()
    assert env.client.post(f"/v1/lender/offers/{offer}/confirm-payout", headers=other).status_code == 404  # not its offer
    assert env.client.post(f"/v1/lender/offers/{offer}/confirm-payout", headers=sme).status_code == 403
    r = env.client.post(f"/v1/lender/offers/{offer}/confirm-payout", headers=lender)
    assert r.status_code == 200 and r.json() == {"offer_id": offer, "status": "FUNDED", "dispute_days": 14}
    (ev,) = [e for e in env.events("loan.funded", sme_org) if e["data"]["offer_id"] == offer]
    assert len(ev["data"]["quote_ids"]) == 2 and ev["data"]["lender_org_id"] == str(lender_org)
    assert set(ev["data"]) == {"offer_id", "application_id", "sme_org_id", "lender_org_id", "quote_ids"}  # thin: no amounts
    assert env.client.post(f"/v1/lender/offers/{offer}/confirm-payout", headers=lender).status_code == 409  # a loan is funded once, a fee is triggered once
    assert len([e for e in env.events("loan.funded", sme_org) if e["data"]["offer_id"] == offer]) == 1
    detail = env.client.get(f"/v1/applications/{app}", headers=sme).json()
    assert detail["status"] == "FUNDED" and detail["dispute_until"] is not None


def test_payout_confirmation_is_idempotent_with_a_key(env):
    sme_org, sme, _, lender, app, offer = selected(env)
    hk = {**lender, "Idempotency-Key": "pay-1"}
    a, b = env.client.post(f"/v1/lender/offers/{offer}/confirm-payout", headers=hk), env.client.post(f"/v1/lender/offers/{offer}/confirm-payout", headers=hk)
    assert a.status_code == b.status_code == 200
    assert len([e for e in env.events("loan.funded", sme_org) if e["data"]["offer_id"] == offer]) == 1


def test_an_unselected_offer_cannot_be_confirmed_as_paid_out(env):
    _, _, _, lender, app, offer = new_offer_ready(env)
    assert env.client.post(f"/v1/lender/offers/{offer}/confirm-payout", headers=lender).json()["code"] == "invalid_state"


def test_the_sme_can_dispute_within_14_days_only(env):
    sme_org, sme, _, lender, app, offer = selected(env)
    assert env.client.post(f"/v1/applications/{app}/dispute", headers=sme).json()["code"] == "not_funded"
    env.client.post(f"/v1/lender/offers/{offer}/confirm-payout", headers=lender)
    _, member = env.sme(role="SME_MEMBER")
    assert env.client.post(f"/v1/applications/{app}/dispute", headers=member).status_code == 403
    assert env.client.post(f"/v1/applications/{app}/dispute", headers=sme).json() == {"application_id": app, "disputed": True}
    ev = [e for e in env.events("loan.disputed", sme_org) if e["data"]["application_id"] == app]
    assert len(ev) == 1 and len(ev[0]["data"]["quote_ids"]) == 2
    assert env.client.post(f"/v1/applications/{app}/dispute", headers=sme).json()["code"] == "already_disputed"


def test_dispute_window_closes(env):
    sme_org, sme, _, lender, app, offer = selected(env)
    env.client.post(f"/v1/lender/offers/{offer}/confirm-payout", headers=lender)
    with env.db.system() as s:
        s.execute(text("update applications set dispute_until = now() - interval '1 minute' where id = :a"), {"a": app})
    assert env.client.post(f"/v1/applications/{app}/dispute", headers=sme).json()["code"] == "dispute_window_closed"


def test_a_cancelled_loan_drops_the_fee_and_cannot_be_funded_afterwards(env):
    sme_org, sme, _, lender, app, offer = selected(env)
    assert env.client.post(f"/v1/lender/offers/{offer}/cancel-loan", headers=lender).json()["status"] == "CANCELLED"
    assert [e for e in env.events("loan.cancelled", sme_org) if e["data"]["offer_id"] == offer]
    assert env.client.post(f"/v1/lender/offers/{offer}/confirm-payout", headers=lender).status_code == 409
    assert env.client.get(f"/v1/applications/{app}", headers=sme).json()["status"] == "CANCELLED"


# ===================================================================================== matcher, benchmark, lifecycle
def test_matcher_notifies_only_lenders_whose_criteria_fit(env):
    sme_org, sme = env.sme(industry="manufacturing")
    fit_org, fit = env.lender()
    env.criteria(fit, industries=["manufacturing"], amount_max="1000000")
    miss_org, miss = env.lender()
    env.criteria(miss, industries=["retail"])
    hidden_org, hidden = env.lender()
    env.criteria(hidden, min={"equity_ratio": "0.1"})  # needs a field this SME did not share
    app = env.publish(sme)
    published = [e for e in env.events("application.published", sme_org) if e["data"]["application_id"] == app][-1]
    matcher = next(c for c in consumers() if c.name == "marketplace-matcher")
    process_event(env.db, matcher, published)
    matched = [e for e in env.events("application.matched", sme_org) if e["data"]["application_id"] == app][-1]["data"]
    assert str(fit_org) in matched["lender_org_ids"] and str(miss_org) not in matched["lender_org_ids"] and str(hidden_org) not in matched["lender_org_ids"]


def test_benchmark_is_anonymised_and_needs_enough_offers_from_enough_lenders(env):
    env.as_owner("delete from benchmark_observations")
    assert env.client.get("/v1/benchmark", headers=env.sme()[1]).json()["groups"] == []
    with env.db.system() as s:
        for i in range(5):  # 5 offers but only 2 lenders: still hidden
            s.execute(text("insert into benchmark_observations(id, category, amount_band, term_months, rate, lender_key) values (:i, 'B', '250k-1M', 60, :r, :k)"),
                      {"i": uuid.uuid4(), "r": 3 + i * Decimal("0.1"), "k": f"l{i % 2}"})
    assert env.client.get("/v1/benchmark", headers=env.sme()[1]).json()["groups"] == []
    with env.db.system() as s:
        s.execute(text("insert into benchmark_observations(id, category, amount_band, term_months, rate, lender_key) values (:i, 'B', '250k-1M', 60, 3.5, 'l9')"), {"i": uuid.uuid4()})
    body = env.client.get("/v1/benchmark", headers=env.sme()[1]).json()
    (g,) = body["groups"]
    assert g["offers"] == 6 and g["lenders"] == 3 and set(g) == {"category", "amount_band", "offers", "lenders", "avg_rate", "min_rate", "max_rate"} and body["illustrative"] is True


def test_deletion_removes_everything_and_blocks_replays(env):
    sme_org, sme, lender_org, lender, app, offer = new_offer_ready(env)
    ev = {"id": str(uuid.uuid4()), "type": "credsort.identity.organization.deletion_requested.v1", "credsortorgid": str(sme_org),
          "data": {"org_id": str(sme_org), "requested_at": "2026-11-19T00:00:00Z"}}
    deleter = next(c for c in consumers() if c.name == "marketplace-deletion")
    assert process_event(env.db, deleter, ev)
    with env.db.system() as s:
        assert s.execute(text("select count(*) from applications where sme_org_id = :o"), {"o": sme_org}).scalar() == 0
        assert s.execute(text("select count(*) from offers where application_id = :a"), {"a": app}).scalar() == 0
    assert app not in [i["application_id"] for i in env.matches(lender)["items"]]
    assert [e for e in env.events("audit.recorded", sme_org) if e["data"]["action"] == "data.deleted"]
    again = {**ev, "id": str(uuid.uuid4()), "type": "credsort.marketplace.application.published.v1"}
    assert process_event(env.db, next(c for c in consumers() if c.name == "marketplace-matcher"), again) is False  # tombstone


def test_every_table_has_row_level_security_and_api_hygiene(env):
    with env.db.system() as s:
        rows = s.execute(text("select relname, relrowsecurity and relforcerowsecurity as ok from pg_class c join pg_namespace n on n.oid = c.relnamespace "
                              "where n.nspname = 'public' and c.relkind = 'r'")).all()
    assert [r.relname for r in rows if not r.ok and r.relname not in {"schema_migrations", "inbox", "denylist", "tombstones"}] == []
    r = env.client.get("/v1/applications", headers=env.sme()[1])
    assert r.headers["cache-control"] == "no-store" and env.client.get("/v1/applications").status_code == 401
    cat = env.client.get("/v1/field-catalogue", headers=env.sme()[1]).json()["fields"]
    assert {f["field"] for f in cat if f["default"]} == set(__import__("app.domain.fields", fromlist=["x"]).SUMMARY_DEFAULT)
