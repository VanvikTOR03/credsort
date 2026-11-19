import json
import uuid
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import text

from conftest import AS_OF
from fixtures import ledger

from credsort_common.background import process_event
from credsort_common.security import ServiceAuth
from credsort_common.testing import service_headers
from credsort_common.upstream import UpstreamClient

from app.consumers import deletion_consumer, pipeline_consumer


def import_event(org, batch_id):
    return {"id": str(uuid.uuid4()), "type": "credsort.accounting.import.completed.v1", "credsortorgid": str(org),
            "data": {"org_id": str(org), "batch_id": str(batch_id), "period_start": "2024-01-01", "period_end": "2025-12-31", "content_hash": "h"}}


def consumer_for(env, ledgers: dict, status=200):
    """A pipeline consumer whose Accounting client is served from `ledgers` (batch id -> ledger json)."""
    def handler(request: httpx.Request):
        batch = request.url.path.split("/")[4]
        if batch not in ledgers:
            return httpx.Response(404, json={"detail": "batch not found"})
        assert request.headers["x-service-token"] and request.url.params["org_id"]
        return httpx.Response(status, json=ledgers[batch])
    client = UpstreamClient("intelligence", "accounting", ServiceAuth("intelligence"), base_url="http://acc", transport=httpx.MockTransport(handler))
    return pipeline_consumer(env.app.state.security, as_of=lambda: AS_OF, client=client)


def run_import(env, org, **ledger_kw):
    batch = uuid.uuid4()
    consumer = consumer_for(env, {str(batch): ledger(batch_id=batch, org_id=org, **ledger_kw)})
    ev = import_event(org, batch)
    assert process_event(env.db, consumer, ev)
    return batch, consumer, ev


def events(env, org, kind):
    with env.db.system() as s:
        return [r.payload for r in s.execute(text("select payload from outbox where org_id = :o and event_type like :t order by created_at"), {"o": org, "t": f"%{kind}%"})]


# ---- the pipeline as an event consumer ------------------------------------------------------
def test_import_event_builds_snapshot_metrics_and_assessment_with_thin_events(env):
    org, h = env.sme()
    assert env.client.get("/v1/profile/current", headers=h).status_code == 404
    run_import(env, org)
    p = env.client.get("/v1/profile/current", headers=h).json()
    assert p["assessment"]["category"] in "ABCD" and p["versions"]["scorecard"] == "sc-1.0.0" and p["assessment"]["confidence"]["demo_data"] is True
    assert {m["code"] for m in p["metrics"]} >= {"revenue", "ebitda_margin", "equity_ratio", "dscr", "receivables_aging"}
    assert isinstance(p["assessment"]["confidence"]["overall"], str) and "not a bank rating" in p["assessment"]["disclaimer"].lower()
    assert all(isinstance(m["value"], (str, type(None))) for m in p["metrics"])  # decimals travel as strings
    for kind in ("snapshot.created", "assessment.created"):
        (ev,) = events(env, org, kind)
        assert "revenue" not in json.dumps(ev["data"]) and ev["credsortorgid"] == str(org)


def test_duplicate_delivery_creates_one_snapshot(env):
    org, _ = env.sme()
    batch, consumer, ev = run_import(env, org)
    assert process_event(env.db, consumer, ev) is False  # same event id: inbox absorbs it
    again = import_event(org, batch)  # a different event for the same batch (re-import): unique (batch, mapping) absorbs it
    process_event(env.db, consumer, again)
    with env.db.session(org) as s:
        assert s.execute(text("select count(*) from snapshots")).scalar() == 1
        assert s.execute(text("select count(*) from assessments")).scalar() == 1


def test_failed_pipeline_records_reason_and_keeps_the_previous_profile(env):
    org, h = env.sme()
    run_import(env, org)
    first = env.client.get("/v1/profile/current", headers=h).json()["assessment"]["id"]
    bad = ledger(org_id=org)
    bad["opening"][0]["amount"] = "123456"  # opening balances no longer balance
    batch = uuid.UUID(bad["batch_id"])
    process_event(env.db, consumer_for(env, {str(batch): bad}), import_event(org, batch))
    assert env.client.get("/v1/profile/current", headers=h).json()["assessment"]["id"] == first  # previous result stays current
    (ev,) = events(env, org, "assessment.failed")
    assert ev["data"]["reason_code"] == "BALANCE_MISMATCH"


def test_batch_gone_is_recorded_not_resurrected(env):
    org, h = env.sme()
    batch = uuid.uuid4()
    process_event(env.db, consumer_for(env, {}), import_event(org, batch))
    assert env.client.get("/v1/profile/current", headers=h).status_code == 404
    assert events(env, org, "assessment.failed")[0]["data"]["reason_code"] == "BATCH_GONE"


def test_accounting_outage_raises_so_the_broker_retries(env):
    org, _ = env.sme()
    def down(request):
        return httpx.Response(503)
    client = UpstreamClient("intelligence", "accounting", ServiceAuth("intelligence"), base_url="http://acc", transport=httpx.MockTransport(down))
    consumer = pipeline_consumer(env.app.state.security, as_of=lambda: AS_OF, client=client)
    from credsort_common.errors import UpstreamUnavailable
    ev = import_event(org, uuid.uuid4())
    with pytest.raises(UpstreamUnavailable):
        process_event(env.db, consumer, ev)
    with env.db.system() as s:  # the remote call happens before the transaction: nothing was recorded, so the retry will run
        assert s.execute(text("select count(*) from inbox where consumer = 'intelligence-pipeline' and event_id = :e"), {"e": ev["id"]}).scalar() == 0


def test_new_assessment_does_not_overwrite_the_old_one(env):
    org, h = env.sme()
    run_import(env, org)
    run_import(env, org, growth=Decimal("0.30"))
    history = env.client.get("/v1/assessments", headers=h).json()
    assert len(history) == 2


# ---- access rules ---------------------------------------------------------------------------
def test_tenants_and_roles_are_isolated(env):
    a, ha = env.sme()
    b, hb = env.sme()
    run_import(env, a)
    aid = env.client.get("/v1/profile/current", headers=ha).json()["assessment"]["id"]
    assert env.client.get(f"/v1/assessments/{aid}", headers=hb).status_code == 404
    assert env.client.get("/v1/profile/current", headers=hb).status_code == 404
    assert env.client.get("/v1/profile/current", headers=env.tokens.headers(org_type="LENDER", role="CREDIT_OFFICER")).status_code == 403
    fid = env.tokens.headers(org_type="FIDUCIARY", role="FIDUCIARY_ADVISOR", on_behalf_of=a, scopes=("VIEW_PROFILE",))
    assert env.client.get("/v1/profile/current", headers=fid).status_code == 200
    nosc = env.tokens.headers(org_type="FIDUCIARY", role="FIDUCIARY_ADVISOR", on_behalf_of=a, scopes=("PREPARE_APPLICATION",))
    assert env.client.get("/v1/profile/current", headers=nosc).status_code == 403  # delegation without VIEW_PROFILE


def test_profile_extract_returns_only_requested_fields_to_the_marketplace(env):
    org, h = env.sme()
    run_import(env, org)
    aid = env.client.get("/v1/profile/current", headers=h).json()["assessment"]["id"]
    path = f"/internal/v1/assessments/{aid}/profile-extract"
    headers = {**h, **service_headers("marketplace", "intelligence")}
    r = env.client.get(path, params={"fields": "assessment_category,ebitda_margin,revenue_band,confidence_band"}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert set(body["fields"]) == {"assessment_category", "ebitda_margin", "revenue_band", "confidence_band"}  # nothing else leaves this service
    assert body["fields"]["revenue_band"] == "1-5M" and body["fields"]["confidence_band"] == "MEDIUM" and body["assessment_id"] == aid
    assert env.client.get(path, params={"fields": "equity_ratio,ledger"}, headers=headers).status_code == 422
    assert env.client.get(path, params={"fields": ""}, headers=headers).status_code == 422
    assert env.client.get(path, params={"fields": "dscr"}, headers=h).status_code == 401  # a user token alone is not enough
    assert env.client.get(path, params={"fields": "dscr"}, headers={**h, **service_headers("advisory", "intelligence")}).status_code == 403
    other = {**env.sme()[1], **service_headers("marketplace", "intelligence")}
    assert env.client.get(path, params={"fields": "dscr"}, headers=other).status_code == 404  # another tenant's assessment


def test_unavailable_metric_is_extracted_as_null_not_zero(env):
    org, h = env.sme()
    run_import(env, org, drop_prior_year=True)
    aid = env.client.get("/v1/profile/current", headers=h).json()["assessment"]["id"]
    r = env.client.get(f"/internal/v1/assessments/{aid}/profile-extract", params={"fields": "revenue_growth"}, headers={**h, **service_headers("marketplace", "intelligence")})
    assert r.json()["fields"]["revenue_growth"] is None


def test_advisory_context_is_aggregates_only(env):
    org, h = env.sme()
    run_import(env, org)
    aid = env.client.get("/v1/profile/current", headers=h).json()["assessment"]["id"]
    r = env.client.get(f"/internal/v1/assessments/{aid}/advisory-context", headers={**h, **service_headers("advisory", "intelligence")})
    assert r.status_code == 200
    blob = json.dumps(r.json())
    assert "journal" not in blob and "entries" not in blob and "debit_account" not in blob
    assert env.client.get(f"/internal/v1/assessments/{aid}/advisory-context", headers={**h, **service_headers("marketplace", "intelligence")}).status_code == 403


# ---- scenarios + entitlements ---------------------------------------------------------------
def test_scenario_runs_on_a_copy_and_is_stored(env):
    org, h = env.sme()
    run_import(env, org)
    aid = env.client.get("/v1/profile/current", headers=h).json()["assessment"]["id"]
    r = env.client.post("/v1/scenarios", json={"assessment_id": aid, "inputs": {"cost_reduction_pct": "10"}}, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["after"]["assessment"]["score"] >= body["before"]["assessment"]["score"] and body["assumptions"]
    assert env.client.get("/v1/profile/current", headers=h).json()["assessment"]["id"] == aid  # baseline unchanged
    bad = env.client.post("/v1/scenarios", json={"assessment_id": aid, "inputs": {"debt_repayment_from_cash": "999999999"}}, headers=h)
    assert bad.status_code == 422


def test_scenarios_follow_the_plan_and_fail_closed_when_billing_is_down(env):
    org, h = env.sme()
    run_import(env, org)
    aid = env.client.get("/v1/profile/current", headers=h).json()["assessment"]["id"]
    env.billing.fail = True  # empty entitlement cache + Billing down: deny rather than guess
    r = env.client.post("/v1/scenarios", json={"assessment_id": aid, "inputs": {"cost_reduction_pct": "5"}}, headers=h)
    assert r.status_code == 503 and r.json()["code"] == "entitlements_unavailable"
    env.billing.fail = False
    assert env.client.post("/v1/scenarios", json={"assessment_id": aid, "inputs": {"cost_reduction_pct": "5"}}, headers=h).status_code == 201
    env.billing.fail = True  # now cached: a Billing outage no longer matters
    assert env.client.post("/v1/scenarios", json={"assessment_id": aid, "inputs": {"cost_reduction_pct": "5"}}, headers=h).status_code == 201
    env.billing.fail = False
    with env.db.system() as s:
        s.execute(text("update entitlements set entitlements = '{PROFILE}' where org_id = :o"), {"o": org})
    r = env.client.post("/v1/scenarios", json={"assessment_id": aid, "inputs": {"cost_reduction_pct": "5"}}, headers=h)
    assert r.status_code == 403 and r.json()["code"] == "feature_not_included"


# ---- lifecycle ------------------------------------------------------------------------------
def test_deletion_removes_all_data_confirms_and_blocks_replays(env):
    org, h = env.sme()
    batch, consumer, _ = run_import(env, org)
    ev = {"id": str(uuid.uuid4()), "type": "credsort.identity.organization.deletion_requested.v1", "credsortorgid": str(org),
          "data": {"org_id": str(org), "requested_at": "2026-11-19T00:00:00Z"}}
    assert process_event(env.db, deletion_consumer(), ev)
    assert env.client.get("/v1/profile/current", headers=h).status_code == 404
    with env.db.system() as s:
        assert s.execute(text("select count(*) from snapshots where org_id = :o"), {"o": org}).scalar() == 0
        audit = s.execute(text("select payload->'data'->>'action' from outbox where event_type like '%audit.recorded%' and org_id = :o order by created_at desc limit 1"), {"o": org}).scalar()
    assert audit == "data.deleted"
    assert process_event(env.db, consumer, import_event(org, batch)) is False  # replay after deletion: tombstone blocks it


def test_every_tenant_table_has_row_level_security(env):
    with env.db.system() as s:
        rows = s.execute(text("select relname, relrowsecurity and relforcerowsecurity as ok from pg_class c join pg_namespace n on n.oid = c.relnamespace "
                              "where n.nspname = 'public' and c.relkind = 'r'")).all()
    exempt = {"schema_migrations", "inbox", "denylist", "tombstones", "mapping_versions", "scorecard_versions"}  # immutable reference data / platform
    assert [r.relname for r in rows if not r.ok and r.relname not in exempt] == []
