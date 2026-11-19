import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from credsort_common.background import process_event

from app import service as svc
from app.main import DELETION, INGEST


def ingest_many(env, org, n=5, **kw):
    evs = [env.event(org, **kw) for _ in range(n)]
    for e in evs:
        assert process_event(env.db, INGEST, e)
    return evs


def verify(env, org):
    with env.db.system() as s:
        return svc.verify_chain(s, org)


def test_records_form_a_hash_chain_per_organization(env):
    a, b = uuid.uuid4(), uuid.uuid4()
    ingest_many(env, a, 5)
    ingest_many(env, b, 2)
    assert verify(env, a) == {"verified": True, "records": 5, "broken_at": None} and verify(env, b)["records"] == 2
    with env.db.system() as s:
        rows = s.execute(text("select seq, prev_hash, hash from audit_log where org_id = :o order by seq"), {"o": a}).all()
    assert [r.seq for r in rows] == [1, 2, 3, 4, 5] and rows[0].prev_hash == "" and all(rows[i].prev_hash == rows[i - 1].hash for i in range(1, 5))


def test_redelivered_events_are_recorded_once(env):
    org = uuid.uuid4()
    e = env.event(org)
    assert process_event(env.db, INGEST, e) and not process_event(env.db, INGEST, e)
    other = {**e, "id": str(uuid.uuid4())}  # same audit record arriving in a different event: absorbed by the unique source id
    process_event(env.db, INGEST, other)
    assert verify(env, org)["records"] == 1


def test_tampering_is_detected_even_by_the_table_owner(env):
    org = uuid.uuid4()
    ingest_many(env, org, 4)
    from sqlalchemy import create_engine
    engine = create_engine(env.owner_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as c:
        c.execute(text("select set_config('app.role', 'SYSTEM', false)"))
        c.execute(text("alter table audit_log disable trigger audit_log_append_only"))
        c.execute(text("update audit_log set action = 'nothing.happened' where org_id = :o and seq = 2"), {"o": org})
        c.execute(text("alter table audit_log enable trigger audit_log_append_only"))
    engine.dispose()
    result = verify(env, org)
    assert result["verified"] is False and result["broken_at"] == 2


def test_the_application_role_cannot_edit_or_delete_records(env):
    org = uuid.uuid4()
    ingest_many(env, org, 2)
    for sql in ("update audit_log set action = 'x' where org_id = :o", "delete from audit_log where org_id = :o"):
        with pytest.raises(DBAPIError):
            with env.db.system() as s:
                s.execute(text(sql), {"o": org})


def test_activity_is_private_labelled_and_attributed(env):
    sme, other, fid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    user = uuid.uuid4()
    process_event(env.db, INGEST, env.event(sme, "application.published", actor=user, acting=sme))
    process_event(env.db, INGEST, env.event(sme, "application.viewed", service="marketplace", acting=other))  # a lender viewed it
    process_event(env.db, INGEST, env.event(sme, "application.updated", acting=fid, behalf=sme))  # a fiduciary acted for the SME
    process_event(env.db, INGEST, env.event(sme, "import.completed", service="accounting"))
    process_event(env.db, INGEST, env.event(other, "offer.submitted"))
    items = env.client.get("/v1/activity", headers=env.tokens.headers(org_id=sme)).json()
    assert [i["by"] for i in items] == ["platform", "delegate", "other", "you"]
    assert items[0]["label"] == "Accounting data imported" and items[2]["label"] == "A lender viewed your shared information"
    assert all("actor_user_id" not in i for i in items)  # personal references are not exposed
    assert env.client.get("/v1/activity", headers=env.tokens.headers(org_id=other)).json()[0]["action"] == "offer.submitted"
    page = env.client.get("/v1/activity?limit=2", headers=env.tokens.headers(org_id=sme)).json()
    assert len(page) == 2 and len(env.client.get(f"/v1/activity?before={page[-1]['seq']}", headers=env.tokens.headers(org_id=sme)).json()) == 2


def test_delegates_need_view_scope(env):
    sme = uuid.uuid4()
    process_event(env.db, INGEST, env.event(sme))
    nope = env.tokens.headers(org_type="FIDUCIARY", role="FIDUCIARY_ADVISOR", on_behalf_of=sme, scopes=("PREPARE_APPLICATION",))
    ok = env.tokens.headers(org_type="FIDUCIARY", role="FIDUCIARY_ADVISOR", on_behalf_of=sme, scopes=("VIEW_PROFILE",))
    assert env.client.get("/v1/activity", headers=nope).json() == [] and len(env.client.get("/v1/activity", headers=ok).json()) == 1


def test_only_platform_admins_verify_chains(env):
    org = uuid.uuid4()
    ingest_many(env, org, 3)
    assert env.client.get(f"/v1/admin/verify/{org}", headers=env.tokens.headers(org_id=org)).status_code == 403
    admin = env.tokens.headers(org_type="PLATFORM", role="PLATFORM_ADMIN")
    assert env.client.get(f"/v1/admin/verify/{org}", headers=admin).json()["verified"] is True


def test_deletion_pseudonymises_people_but_keeps_the_trail_and_the_chain(env):
    org, user = uuid.uuid4(), uuid.uuid4()
    process_event(env.db, INGEST, env.event(org, actor=user, acting=org))
    process_event(env.db, INGEST, env.event(org, "offer.selected", actor=user, acting=org))
    ev = {"id": str(uuid.uuid4()), "type": "credsort.identity.organization.deletion_requested.v1", "credsortorgid": str(org), "data": {"org_id": str(org), "requested_at": "x"}}
    assert process_event(env.db, DELETION, ev)
    with env.db.system() as s:
        assert s.execute(text("select count(*) from audit_log where org_id = :o and actor_user_id is not null"), {"o": org}).scalar() == 0
    assert verify(env, org)["verified"] is True  # the hash does not cover personal references
    with env.db.system() as s:  # the deletion confirmation itself was emitted through the outbox
        assert s.execute(text("select count(*) from outbox where event_type like '%audit.audit.recorded%' and org_id = :o"), {"o": org}).scalar() == 1


def test_rls_enabled(env):
    with env.db.system() as s:
        rows = s.execute(text("select relname, relrowsecurity and relforcerowsecurity as ok from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind = 'r'")).all()
    assert [r.relname for r in rows if not r.ok and r.relname not in {"schema_migrations", "inbox", "denylist", "tombstones"}] == []
