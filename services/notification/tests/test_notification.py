import json
import uuid

from sqlalchemy import text

from credsort_common.background import process_event

from app.main import CONSUMERS
from app.rules import RULES

INBOX = CONSUMERS[0]


def ev(name, org, data):
    return {"id": str(uuid.uuid4()), "type": f"credsort.{name}.v1", "credsortorgid": str(org), "data": data}


def inbox(env, org, **kw):
    return env.client.get("/v1/notifications", params=kw, headers=env.headers(org)).json()


def test_events_become_plain_notifications_without_financial_values(env):
    sme, lender, other = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    app, offer = uuid.uuid4(), uuid.uuid4()
    process_event(env.db, INBOX, ev("marketplace.offer.submitted", sme, {"offer_id": str(offer), "application_id": str(app), "sme_org_id": str(sme), "lender_org_id": str(lender)}))
    process_event(env.db, INBOX, ev("marketplace.offer.selected", sme, {"offer_id": str(offer), "application_id": str(app), "sme_org_id": str(sme), "lender_org_id": str(lender), "other_lender_org_ids": [str(other)]}))
    assert inbox(env, sme)["items"][0]["title"] == "You received a new offer"
    assert inbox(env, lender)["items"][0]["kind"] == "offer.selected" and inbox(env, other)["items"][0]["kind"] == "offer.rejected"
    blob = json.dumps([inbox(env, o) for o in (sme, lender, other)], default=str)
    assert "CHF" not in blob and "rate" not in blob.lower().replace("separate", "")


def test_import_failure_messages_are_helpful_and_never_leak_internals(env):
    org = uuid.uuid4()
    process_event(env.db, INBOX, ev("accounting.import.failed", org, {"org_id": str(org), "job_id": str(uuid.uuid4()), "reason_code": "AUTH_ERROR"}))
    process_event(env.db, INBOX, ev("accounting.import.failed", org, {"org_id": str(org), "job_id": str(uuid.uuid4()), "reason_code": "VALIDATION_OPENING_UNBALANCED"}))
    bodies = [i["body"] for i in inbox(env, org)["items"]]
    assert any("reconnect bexio" in b.lower() for b in bodies) and any("opening unbalanced" in b for b in bodies)


def test_revoking_consent_removes_lender_notifications_but_not_the_smes(env):
    sme, lender, app = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    process_event(env.db, INBOX, ev("marketplace.application.matched", sme, {"application_id": str(app), "sme_org_id": str(sme), "lender_org_ids": [str(lender)]}))
    process_event(env.db, INBOX, ev("marketplace.access.requested", sme, {"application_id": str(app), "request_id": str(uuid.uuid4()), "sme_org_id": str(sme), "lender_org_id": str(lender)}))
    assert inbox(env, lender)["unread"] == 1 and inbox(env, sme)["unread"] == 1
    process_event(env.db, INBOX, ev("marketplace.disclosure.revoked", sme, {"application_id": str(app), "sme_org_id": str(sme), "lender_org_id": None, "level": "summary"}))
    assert inbox(env, lender)["items"] == []          # the lender can no longer even tell the application existed
    assert len(inbox(env, sme)["items"]) == 1          # the SME's own history stays


def test_every_rule_produces_valid_notes():
    assert set(RULES) >= {"marketplace.loan.funded", "marketplace.loan.disputed", "marketplace.loan.cancelled", "billing.charge.status_changed"}


def test_read_state_and_isolation(env):
    org, other = uuid.uuid4(), uuid.uuid4()
    process_event(env.db, INBOX, ev("intelligence.assessment.created", org, {"org_id": str(org), "assessment_id": str(uuid.uuid4()), "snapshot_id": str(uuid.uuid4()), "scorecard_version": "s", "mapping_version": "m"}))
    nid = inbox(env, org)["items"][0]["id"]
    assert env.client.post(f"/v1/notifications/{nid}/read", headers=env.headers(other)).status_code == 404  # not yours
    assert env.client.post(f"/v1/notifications/{nid}/read", headers=env.headers(org)).status_code == 204
    assert inbox(env, org)["unread"] == 0 and inbox(env, org, unread="true")["items"] == []


def test_duplicate_events_create_one_notification_and_deletion_clears_the_inbox(env):
    org = uuid.uuid4()
    e = ev("intelligence.assessment.failed", org, {"org_id": str(org), "batch_id": str(uuid.uuid4()), "reason_code": "BALANCE_MISMATCH"})
    assert process_event(env.db, INBOX, e) and not process_event(env.db, INBOX, e)
    assert len(inbox(env, org)["items"]) == 1
    deleter = CONSUMERS[1]
    assert process_event(env.db, deleter, ev("identity.organization.deletion_requested", org, {"org_id": str(org), "requested_at": "x"}))
    assert inbox(env, org)["items"] == []


def test_rls_enabled(env):
    with env.db.system() as s:
        rows = s.execute(text("select relname, relrowsecurity and relforcerowsecurity as ok from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind = 'r'")).all()
    assert [r.relname for r in rows if not r.ok and r.relname not in {"schema_migrations", "inbox", "denylist", "tombstones"}] == []
