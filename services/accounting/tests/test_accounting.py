import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text

from conftest import AS_OF
from credsort_common.testing import service_headers

from app.domain.ledger import CanonicalLedger, Entry, validate
from app.plugins.synthetic import PROFILES, build_ledger
from app.worker import claim_next, run_one


# ---- pure domain ----------------------------------------------------------------------------
@pytest.mark.parametrize("dataset", sorted(PROFILES))
def test_synthetic_ledgers_are_consistent_and_deterministic(dataset):
    a, b = build_ledger(dataset, AS_OF), build_ledger(dataset, AS_OF)
    assert validate(a) == []  # double-entry, opening balance equation, dates, duplicates
    assert sum(a.opening.values(), Decimal(0)) == 0
    assert [(e.reference, e.amount) for e in a.entries] == [(e.reference, e.amount) for e in b.entries]
    assert a.period_start == date(2024, 1, 1) and a.period_end == date(2025, 12, 31)


def test_validation_catches_each_accounting_error():
    base = build_ledger("muster", AS_OF)
    bad_open = CanonicalLedger("X", base.period_start, base.period_end, base.accounts, {**base.opening, "1020": base.opening["1020"] + 1}, base.entries)
    assert {i.code for i in validate(bad_open)} == {"OPENING_UNBALANCED"}
    e = base.entries[0]
    dup = CanonicalLedger("X", base.period_start, base.period_end, base.accounts, base.opening, [*base.entries, e])
    assert "DUPLICATE_ENTRY" in {i.code for i in validate(dup)}
    odd = CanonicalLedger("X", base.period_start, base.period_end, base.accounts, base.opening,
                          [Entry(date(2030, 1, 1), "1020", "9999", Decimal("-5"), "z-1")])
    assert {"OUT_OF_PERIOD", "UNKNOWN_ACCOUNT", "NON_POSITIVE_AMOUNT"} <= {i.code for i in validate(odd)}
    assert "NO_ENTRIES" in {i.code for i in validate(CanonicalLedger("X", base.period_start, base.period_end, base.accounts, {}, []))}


# ---- import flow ----------------------------------------------------------------------------
def test_import_flow_writes_batch_and_emits_a_thin_event(env):
    org, h = env.sme()
    cid = env.connect(h)
    r = env.start(h, cid)
    assert r.status_code == 202 and r.headers["location"].startswith("/v1/import-jobs/")
    assert env.client.get(r.headers["location"], headers=h).json()["status"] == "PENDING"
    assert run_one(env.db, AS_OF) == "COMPLETED"
    job = env.client.get(r.headers["location"], headers=h).json()
    assert job["status"] == "COMPLETED" and job["batch_id"]
    with env.db.system() as s:
        ev = s.execute(text("select payload from outbox where event_type like '%import.completed%' and org_id = :o"), {"o": org}).scalar()
        n = s.execute(text("select count(*) from journal_entries where batch_id = :b"), {"b": job["batch_id"]}).scalar()
    assert n > 100
    assert set(ev["data"]) == {"org_id", "batch_id", "period_start", "period_end", "content_hash"}  # thin: no ledger values
    assert ev["credsortorgid"] == str(org) and ev["traceparent"]


def test_reimporting_identical_data_creates_no_new_batch_or_event(env):
    org, h = env.sme()
    cid = env.connect(h)
    env.start(h, cid)
    run_one(env.db, AS_OF)
    env.start(h, cid)
    assert run_one(env.db, AS_OF) == "REUSED"
    with env.db.system() as s:
        assert s.execute(text("select count(*) from import_batches where org_id = :o"), {"o": org}).scalar() == 1
        assert s.execute(text("select count(*) from outbox where event_type like '%import.completed%' and org_id = :o"), {"o": org}).scalar() == 1


def test_only_one_active_job_per_connection_and_idempotency_key(env):
    _, h = env.sme()
    cid = env.connect(h)
    first = env.start(h, cid, **{"Idempotency-Key": "abc"})
    again = env.start(h, cid, **{"Idempotency-Key": "abc"})
    assert first.status_code == again.status_code == 202 and first.json()["id"] == again.json()["id"]  # same key: same job
    other = env.start(h, cid)  # a different request while one is active
    assert other.status_code == 409 and other.json()["code"] == "import_in_progress"
    reused = env.client.post("/v1/import-jobs", json={"connection_id": str(uuid.uuid4())}, headers={**h, "Idempotency-Key": "abc"})
    assert reused.status_code == 409 and reused.json()["code"] == "idempotency_key_reused"


def test_crashed_worker_job_is_reclaimed_after_the_lease_and_finishes_once(env):
    org, h = env.sme()
    cid = env.connect(h)
    jid = env.start(h, cid).json()["id"]
    job = claim_next(env.db)  # worker A claims and "crashes" (never finishes)
    assert job and str(job.id) == jid
    assert claim_next(env.db) is None  # lease still valid: nobody else may take it
    with env.db.system() as s:
        s.execute(text("update import_jobs set locked_until = now() - interval '1 minute' where id = :i"), {"i": jid})
    assert run_one(env.db, AS_OF) == "COMPLETED"
    with env.db.system() as s:
        assert s.execute(text("select count(*) from import_batches where org_id = :o"), {"o": org}).scalar() == 1
        assert s.execute(text("select attempts from import_jobs where id = :i"), {"i": jid}).scalar() == 2


def test_failed_import_reports_a_reason_code_and_event(env):
    org, h = env.sme()
    cid = env.connect(h, source="BEXIO")  # no OAuth token stored: authorization error, never retried
    jid = env.start(h, cid).json()["id"]
    assert run_one(env.db, AS_OF) == "AUTH_ERROR"
    job = env.client.get(f"/v1/import-jobs/{jid}", headers=h).json()
    assert job["status"] == "FAILED" and job["failure_reason"] == "AUTH_ERROR" and job["batch_id"] is None
    with env.db.system() as s:
        assert s.execute(text("select payload->'data'->>'reason_code' from outbox where event_type like '%import.failed%' and org_id = :o"), {"o": org}).scalar() == "AUTH_ERROR"
    assert env.start(h, cid).status_code == 202  # a retry is a NEW job


# ---- confidentiality ------------------------------------------------------------------------
def test_other_tenants_cannot_see_or_use_connections_and_jobs(env):
    _, a = env.sme()
    _, b = env.sme()
    cid = env.connect(a)
    jid = env.start(a, cid).json()["id"]
    assert env.client.get(f"/v1/import-jobs/{jid}", headers=b).status_code == 404
    assert env.client.get("/v1/connections", headers=b).json() == []
    assert env.start(b, cid).status_code == 404
    assert env.client.delete(f"/v1/connections/{cid}", headers=b).status_code == 404


def test_roles_and_delegation_boundaries(env):
    assert env.client.get("/v1/connections", headers=env.tokens.headers(org_type="LENDER", role="CREDIT_OFFICER")).status_code == 403
    sme_org = uuid.uuid4()
    fid = env.tokens.headers(org_type="FIDUCIARY", role="FIDUCIARY_ADVISOR", on_behalf_of=sme_org, scopes=("VIEW_PROFILE",))
    assert env.client.get("/v1/connections", headers=fid).status_code == 200  # may view
    assert env.client.post("/v1/connections", json={"source_type": "SYNTHETIC"}, headers=fid).status_code == 403  # may not prepare
    undelegated = env.tokens.headers(org_type="FIDUCIARY", role="FIDUCIARY_ADVISOR")
    assert env.client.get("/v1/connections", headers=undelegated).status_code == 403


def test_ledger_claim_check_needs_the_intelligence_service_and_the_owning_org(env):
    org, h = env.sme()
    env.start(h, env.connect(h))
    run_one(env.db, AS_OF)
    with env.db.system() as s:
        batch = s.execute(text("select id from import_batches where org_id = :o"), {"o": org}).scalar()
    path = f"/internal/v1/batches/{batch}/ledger"
    assert env.client.get(path, params={"org_id": str(org)}, headers=env.tokens.headers()).status_code == 401  # a user token is not a service token
    assert env.client.get(path, params={"org_id": str(org)}, headers=service_headers("marketplace", "accounting")).status_code == 403  # wrong caller
    ok = env.client.get(path, params={"org_id": str(org)}, headers=service_headers("intelligence", "accounting"))
    assert ok.status_code == 200
    body = ok.json()
    assert body["source_type"] == "SYNTHETIC" and len(body["entries"]) > 100 and isinstance(body["entries"][0]["amount"], str)
    other = env.client.get(path, params={"org_id": str(uuid.uuid4())}, headers=service_headers("intelligence", "accounting"))
    assert other.status_code == 404  # wrong organization: RLS hides the batch


def test_every_tenant_table_has_row_level_security(env):
    with env.db.system() as s:
        rows = s.execute(text("select relname, relrowsecurity and relforcerowsecurity as ok from pg_class c join pg_namespace n on n.oid = c.relnamespace "
                              "where n.nspname = 'public' and c.relkind = 'r'")).all()
    assert [r.relname for r in rows if not r.ok and r.relname not in {"schema_migrations", "inbox", "denylist", "tombstones"}] == []
