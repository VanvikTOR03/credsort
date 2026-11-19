import json
import threading
import time
import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from credsort_common import event_catalog
from credsort_common.background import Consumer, OutboxRelay, process_event
from credsort_common.broker import InMemoryBroker, MAX_ATTEMPTS, PgDevBroker, retry_delay
from credsort_common.db import Database, set_org
from credsort_common.errors import Unauthorized, UpstreamHTTPError, UpstreamUnavailable
from credsort_common.events import emit
from credsort_common.migrate import provision, service_urls, migrate
from credsort_common.security import AccessContext, Denylist, JwksCache, RS256Verifier, ServiceAuth, context_from_claims, new_context_claims, KeyStore
from credsort_common.testing import TestTokens, provision_service, make_security
from credsort_common.upstream import UpstreamClient

EMPTY = Path(__file__).parent / "empty_migrations"


@pytest.fixture(scope="module")
def db(pg):
    EMPTY.mkdir(exist_ok=True)
    (EMPTY / "0001_t.sql").write_text(
        "create table items (id uuid primary key, org_id uuid not null, label text);"
        "alter table items enable row level security; alter table items force row level security;"
        "create policy tenant on items using (org_id = app_org() or app_role() = 'SYSTEM') with check (org_id = app_org() or app_role() = 'SYSTEM');")
    app_url, _ = provision_service(pg, "audit", EMPTY)
    return Database(app_url, "audit")


# ---- catalogue ---------------------------------------------------------------------------------
def test_event_catalog_is_thin_and_strict():
    for name, schema in event_catalog.CATALOG.items():
        assert schema["additionalProperties"] is False
        assert not set(schema["properties"]) & event_catalog.FORBIDDEN_FIELDS, name


def test_emit_rejects_unknown_and_extra_fields(db):
    org = uuid.uuid4()
    with pytest.raises(ValueError):
        with db.session(org) as s:
            emit(s, "identity", "identity.organization.suspended", org, "org/x", {"org_id": str(org), "revenue": "1"})
    with pytest.raises(KeyError):
        with db.session(org) as s:
            emit(s, "identity", "identity.nope", org, "x", {})


# ---- RLS ---------------------------------------------------------------------------------------
def test_rls_isolates_tenants_and_system_sees_all(db):
    a, b = uuid.uuid4(), uuid.uuid4()
    with db.session(a) as s:
        s.execute(text("insert into items values (:i, :o, 'a')"), {"i": uuid.uuid4(), "o": a})
    with db.session(b) as s:
        s.execute(text("insert into items values (:i, :o, 'b')"), {"i": uuid.uuid4(), "o": b})
        assert s.execute(text("select count(*) from items")).scalar() == 1
        assert s.execute(text("select count(*) from items where org_id = :a"), {"a": a}).scalar() == 0
    with pytest.raises(Exception):  # cannot write rows for another tenant (own transaction: a failed statement aborts it)
        with db.session(b) as s:
            s.execute(text("insert into items values (:i, :o, 'x')"), {"i": uuid.uuid4(), "o": a})
    with db.system() as s:
        assert s.execute(text("select count(*) from items")).scalar() >= 2


def test_runtime_role_cannot_bypass_rls_or_create_tables(db):
    with pytest.raises(Exception):
        with db.session(uuid.uuid4()) as s:
            s.execute(text("create table evil (x int)"))
    with db.session() as s:  # no org set: sees nothing
        assert s.execute(text("select count(*) from items")).scalar() == 0


def test_outbox_unreadable_for_requests(db):
    org = uuid.uuid4()
    with db.session(org) as s:
        emit(s, "identity", "identity.organization.suspended", org, f"org/{org}", {"org_id": org})
        assert s.execute(text("select count(*) from outbox")).scalar() == 0  # insert-only for requests
    with db.system() as s:
        assert s.execute(text("select count(*) from outbox where org_id = :o"), {"o": org}).scalar() == 1


# ---- outbox -> broker -> inbox -------------------------------------------------------------------
def test_outbox_relay_delivers_once_and_inbox_absorbs_duplicates(db, pg):
    broker = PgDevBroker(pg)
    seen = []
    consumer = Consumer("t1", ["identity.organization.suspended.*"], lambda s, ev: seen.append(ev["id"]))
    broker.declare_consumer("t1", consumer.bindings)
    org = uuid.uuid4()
    with db.session(org) as s:
        ev = emit(s, "identity", "identity.organization.suspended", org, f"org/{org}", {"org_id": org})
    relay = OutboxRelay(db, broker, threading.Event())
    assert relay.drain_once() >= 1
    stop = threading.Event()
    t = threading.Thread(target=broker.consume, args=("t1", lambda e: process_event(db, consumer, e), stop), daemon=True)
    t.start()
    time.sleep(1.2)
    # redelivery of the same event (at-least-once) must not repeat the side effect
    broker.publish(ev)
    time.sleep(1.2)
    stop.set()
    assert seen.count(ev["id"]) == 1


def test_failed_handler_is_retried_then_dead_lettered():
    broker = InMemoryBroker()
    broker.declare_consumer("q", ["a.b.*"])
    calls = []
    def boom(_):
        calls.append(1)
        raise RuntimeError("poison")
    broker.publish({"type": "credsort.a.b.v1", "id": "1"})
    broker.drain("q", boom)
    assert len(calls) == MAX_ATTEMPTS and len(broker.dead["q"]) == 1


def test_tombstoned_organization_events_are_not_applied(db):
    org = uuid.uuid4()
    with db.system() as s:
        s.execute(text("insert into tombstones(org_id) values (:o)"), {"o": org})
    seen = []
    consumer = Consumer("t2", ["x.*"], lambda s, ev: seen.append(ev))
    ev = {"id": str(uuid.uuid4()), "type": "credsort.marketplace.application.closed.v1", "credsortorgid": str(org), "data": {}}
    assert process_event(db, consumer, ev) is False and not seen


# ---- security ----------------------------------------------------------------------------------
def test_context_token_verification():
    tokens = TestTokens()
    sec = make_security("marketplace", tokens)
    org = uuid.uuid4()
    claims = sec.context_verifier.verify(tokens.token(org_id=org))
    ctx = context_from_claims(claims)
    assert ctx.org_id == org and ctx.effective_org_id == org
    with pytest.raises(Unauthorized):
        sec.context_verifier.verify(tokens.token(now=int(time.time()) - 3600))  # expired
    other = TestTokens()  # different signing key
    with pytest.raises(Unauthorized):
        sec.context_verifier.verify(other.token())
    with pytest.raises(Unauthorized):
        sec.context_verifier.verify("not.a.jwt")


def test_wrong_audience_rejected():
    ks = KeyStore.generate()
    claims = new_context_claims(user_id=uuid.uuid4(), org_id=uuid.uuid4(), org_type="SME", org_name="x", role="SME_ADMIN")
    claims["aud"] = "someone-else"
    verifier = RS256Verifier(JwksCache.static(ks), audience="credsort-services", issuer="credsort-identity")
    with pytest.raises(Unauthorized):
        verifier.verify(ks.sign(claims))


def test_denylist_blocks_tokens_issued_before_revocation():
    user, org = uuid.uuid4(), uuid.uuid4()
    now = time.time()
    dl = Denylist(lambda: [(user, org, None, now)])
    assert dl.is_denied(user, org, int(now) - 10)
    assert not dl.is_denied(user, org, int(now) + 10)  # issued after the revocation: allowed
    assert not dl.is_denied(uuid.uuid4(), org, int(now) - 10)
    org_dl = Denylist(lambda: [(None, org, None, now)])
    assert org_dl.is_denied(user, org, int(now) - 5)
    sme = uuid.uuid4()  # a revoked delegation only blocks tokens acting on behalf of that SME
    deleg = Denylist(lambda: [(None, org, sme, now)])
    assert deleg.is_denied(user, org, int(now) - 5, on_behalf_of=sme)
    assert not deleg.is_denied(user, org, int(now) - 5)
    assert not deleg.is_denied(user, org, int(now) - 5, on_behalf_of=uuid.uuid4())


def test_retries_back_off_for_hours_before_dead_lettering():
    assert retry_delay(1) == 5 and retry_delay(3) == 120 and retry_delay(99) == 3600
    assert MAX_ATTEMPTS >= 10


def test_service_tokens_need_allowed_callers():
    issuer, verifier = ServiceAuth("marketplace"), ServiceAuth("intelligence")
    assert verifier.verify(issuer.issue("intelligence"), "intelligence") == "marketplace"
    with pytest.raises(Unauthorized):
        verifier.verify(issuer.issue("billing"), "intelligence")  # audience is restricted


# ---- upstream client ---------------------------------------------------------------------------
def make_client(handler, caller="marketplace", target="intelligence"):
    return UpstreamClient(caller, target, ServiceAuth(caller), base_url="http://up", transport=httpx.MockTransport(handler))


def test_call_inventory_is_enforced():
    c = make_client(lambda r: httpx.Response(200, json={}))
    with pytest.raises(PermissionError):
        c.get("/internal/v1/batches/123/ledger")  # marketplace may not read ledgers
    assert c.get("/internal/v1/assessments/abc/profile-extract") == {}
    with pytest.raises(PermissionError):
        make_client(lambda r: httpx.Response(200, json={}), "billing", "marketplace").get("/internal/v1/anything")


def test_get_is_retried_but_post_and_auth_errors_are_not():
    calls = {"n": 0}
    def flaky(request):
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] < 3 else httpx.Response(200, json={"ok": True})
    assert make_client(flaky).get("/internal/v1/assessments/x/profile-extract") == {"ok": True} and calls["n"] == 3
    calls["n"] = 0
    def forbidden(request):
        calls["n"] += 1
        return httpx.Response(403, json={"detail": "no"})
    with pytest.raises(UpstreamHTTPError):
        make_client(forbidden).get("/internal/v1/assessments/x/profile-extract")
    assert calls["n"] == 1
    with pytest.raises(UpstreamUnavailable):
        make_client(lambda r: httpx.Response(503), "marketplace", "billing").post("/internal/v1/quotes", json={})


def test_circuit_breaker_opens_after_repeated_failures():
    c = make_client(lambda r: httpx.Response(500, json={}))
    for _ in range(5):
        with pytest.raises(UpstreamHTTPError):
            c.get("/internal/v1/assessments/x/profile-extract")
    with pytest.raises(UpstreamUnavailable) as err:
        c.get("/internal/v1/assessments/x/profile-extract")
    assert err.value.code == "circuit_open"


def test_decimals_are_serialized_as_strings_not_floats():
    from decimal import Decimal
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import credsort_common.money  # noqa: F401  (installs the encoder)
    app = FastAPI()

    @app.get("/x")
    def x():
        return {"amount": Decimal("170000.0000"), "ratio": Decimal("0.0215")}
    assert TestClient(app).get("/x").json() == {"amount": "170000.0000", "ratio": "0.0215"}
