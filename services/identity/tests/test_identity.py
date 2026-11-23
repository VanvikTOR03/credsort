import uuid

import jwt
import pytest
from sqlalchemy import text

from conftest import uniq

SME = {"type": "SME", "legal_name": "Muster AG", "uid": "CHE-123.456.789", "legal_form": "AG", "industry": "manufacturing", "employees": 25}


def test_onboarding_verifies_synthetic_sme_but_lenders_wait_for_admin(env):
    sme = env.onboard(uniq(), **SME)
    assert sme["kyb_status"] == "VERIFIED"
    lender = env.onboard(uniq(), type="LENDER", legal_name="Regionalbank AG")
    assert lender["kyb_status"] == "PENDING"


def test_context_token_carries_org_role_and_kyb(env):
    email = uniq()
    org = env.onboard(email, **SME)
    headers, body = env.ctx_headers(email, org["id"])
    claims = jwt.decode(headers["Authorization"].split()[1], options={"verify_signature": False})
    assert claims["org_id"] == org["id"] and claims["role"] == "SME_ADMIN" and claims["kyb_status"] == "VERIFIED"
    assert claims["industry"] == "manufacturing" and claims["exp"] - claims["iat"] == 120 and claims["aud"] == "credsort-services"
    assert env.client.get("/v1/organizations/current", headers=headers).json()["legal_name"] == "Muster AG"


def test_unknown_login_gets_no_account_and_foreign_org_is_refused(env):
    r = env.client.post("/v1/context-tokens", json={}, headers=env.user(uniq()))
    assert r.status_code == 404 and r.json()["code"] == "no_account"
    a, b = uniq(), uniq()
    env.onboard(a, **SME)
    org_b = env.onboard(b, **SME)
    r = env.client.post("/v1/context-tokens", json={"org_id": org_b["id"]}, headers=env.user(a))
    assert r.status_code == 403 and r.json()["code"] == "not_a_member"


def test_tokens_require_a_valid_user_token(env):
    assert env.client.post("/v1/context-tokens", json={}).status_code == 401
    assert env.client.post("/v1/context-tokens", json={}, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_tenant_isolation_in_the_database(env):
    a, b = env.onboard(uniq(), **SME), env.onboard(uniq(), **SME)
    with env.db.session(uuid.UUID(a["id"])) as s:
        ids = {str(r.id) for r in s.execute(text("select id from organizations")).all()}
    assert ids == {a["id"]}  # RLS: another organization is invisible even to a raw query


def test_removing_a_member_revokes_access_and_emits_an_event(env):
    admin = uniq()
    org = env.onboard(admin, **SME)
    h, _ = env.ctx_headers(admin, org["id"])
    colleague = uniq()
    r = env.client.post("/v1/members", json={"email": colleague, "display_name": "Cleo", "role": "SME_MEMBER"}, headers=h)
    assert r.status_code == 201
    member_id = r.json()["user_id"]
    assert env.client.delete(f"/v1/members/{member_id}", headers=h).status_code == 204
    with env.db.system() as s:
        n = s.execute(text("select count(*) from outbox where event_type like '%membership.revoked%' and payload->'data'->>'user_id' = :u"), {"u": member_id}).scalar()
    assert n == 1
    r = env.client.post("/v1/context-tokens", json={"org_id": org["id"]}, headers=env.user(colleague))
    assert r.status_code in (403, 404)  # membership revoked: no token any more


def test_member_cannot_manage_members(env):
    admin, member = uniq(), uniq()
    org = env.onboard(admin, **SME)
    h, _ = env.ctx_headers(admin, org["id"])
    env.client.post("/v1/members", json={"email": member, "display_name": "M", "role": "SME_MEMBER"}, headers=h)
    mh, _ = env.ctx_headers(member, org["id"])
    assert env.client.post("/v1/members", json={"email": uniq(), "display_name": "X", "role": "SME_MEMBER"}, headers=mh).status_code == 403


def test_delegation_scopes_never_include_selection_and_tokens_carry_them(env):
    sme_email, fid_email = uniq(), uniq()
    sme = env.onboard(sme_email, **SME)
    fid = env.onboard(fid_email, type="FIDUCIARY", legal_name="Treuhand Muster")
    sh, _ = env.ctx_headers(sme_email, sme["id"])
    bad = env.client.post("/v1/delegations", json={"fiduciary_org_id": fid["id"], "scopes": ["SELECT_OFFER"]}, headers=sh)
    assert bad.status_code == 422
    ok = env.client.post("/v1/delegations", json={"fiduciary_org_id": fid["id"], "scopes": ["VIEW_PROFILE"]}, headers=sh)
    assert ok.status_code == 201
    fh, body = env.ctx_headers(fid_email, fid["id"], on_behalf_of=sme["id"])
    claims = jwt.decode(fh["Authorization"].split()[1], options={"verify_signature": False})
    assert claims["on_behalf_of"] == sme["id"] and claims["scopes"] == ["VIEW_PROFILE"] and claims["org_id"] == fid["id"]
    # a delegated token cannot grant delegations itself
    assert env.client.post("/v1/delegations", json={"fiduciary_org_id": fid["id"]}, headers=fh).status_code == 403
    # revoking removes the ability to obtain delegated tokens
    delegation_id = env.client.get("/v1/delegations", headers=sh).json()[0]["id"]
    assert env.client.delete(f"/v1/delegations/{delegation_id}", headers=sh).status_code == 204
    r = env.client.post("/v1/context-tokens", json={"org_id": fid["id"], "on_behalf_of": sme["id"]}, headers=env.user(fid_email))
    assert r.status_code == 403 and r.json()["code"] == "no_delegation"


def test_referral_code_is_attributed_once_and_published(env):
    fid_email = uniq()
    fid = env.onboard(fid_email, type="FIDUCIARY", legal_name="Treuhand Referrer")
    fh, _ = env.ctx_headers(fid_email, fid["id"])
    code = env.client.get("/v1/organizations/current", headers=fh).json()["referral_code"]
    sme = env.onboard(uniq(), **SME, referral_code=code)
    with env.db.system() as s:
        ref = s.execute(text("select referred_by_org_id from organizations where id = :i"), {"i": sme["id"]}).scalar()
        ev = s.execute(text("select payload->'data'->>'referred_by_org_id' from outbox where event_type like '%organization.created%' and org_id = :o"), {"o": sme["id"]}).scalar()
    assert str(ref) == fid["id"] and ev == fid["id"]
    r = env.client.post("/v1/organizations", json={**SME, "referral_code": "CS-NOPE00"}, headers=env.user(uniq()))
    assert r.status_code == 422


def test_admin_endpoints_need_platform_admin_and_verify_lenders(env):
    admin_email = uniq()
    lender = env.onboard(uniq(), type="LENDER", legal_name="Kantonalbank X")
    # create a platform org + admin the way operators do (seed): directly in the database
    with env.db.system() as s:
        pid, uid_ = uuid.uuid4(), uuid.uuid4()
        s.execute(text("insert into organizations(id, type, legal_name, kyb_status, referral_code) values (:i, 'PLATFORM', 'CredSort', 'VERIFIED', :c)"), {"i": pid, "c": f"CS-{uuid.uuid4().hex[:6]}"})
        s.execute(text("insert into users(id, email, display_name) values (:i, :e, 'Ops')"), {"i": uid_, "e": admin_email})
        s.execute(text("insert into memberships(id, user_id, org_id, role) values (:i, :u, :o, 'PLATFORM_ADMIN')"), {"i": uuid.uuid4(), "u": uid_, "o": pid})
    sme_h, _ = env.ctx_headers(*(lambda e: (e, env.onboard(e, **SME)["id"]))(uniq()))
    assert env.client.get("/v1/admin/organizations", headers=sme_h).status_code == 403
    ah, _ = env.ctx_headers(admin_email, pid)
    listed = env.client.get("/v1/admin/organizations?kyb_status=PENDING", headers=ah).json()
    assert str(lender["id"]) in {str(o["id"]) for o in listed}
    assert env.client.post(f"/v1/admin/organizations/{lender['id']}/verify", headers=ah).json()["kyb_status"] == "VERIFIED"
    assert env.client.post(f"/v1/admin/organizations/{lender['id']}/suspend", headers=ah).status_code == 200


def test_suspended_organizations_get_no_tokens(env):
    email = uniq()
    org = env.onboard(email, **SME)
    with env.db.system() as s:
        s.execute(text("update organizations set status = 'SUSPENDED' where id = :i"), {"i": org["id"]})
    assert env.client.post("/v1/context-tokens", json={}, headers=env.user(email)).status_code == 403


def test_api_hygiene(env):
    r = env.client.get("/v1/organizations/current", headers=env.tokens.headers())
    assert r.headers["cache-control"] == "no-store" and "x-request-id" in r.headers and "traceparent" in r.headers
    assert env.client.get("/v1/organizations/current").status_code == 401
    r = env.client.post("/v1/organizations", json={"type": "SME", "legal_name": "x"}, headers=env.user(uniq()))
    assert r.status_code == 422 and r.headers["content-type"].startswith("application/problem+json")
    assert env.client.get("/.well-known/jwks.json").json()["keys"][0]["alg"] == "RS256"


def test_every_tenant_table_has_row_level_security(env):
    with env.db.system() as s:
        rows = s.execute(text("select relname, relrowsecurity, relforcerowsecurity from pg_class c join pg_namespace n on n.oid = c.relnamespace "
                              "where n.nspname = 'public' and c.relkind = 'r'")).all()
    missing = [r.relname for r in rows if not (r.relrowsecurity and r.relforcerowsecurity) and r.relname not in {"schema_migrations", "inbox", "denylist", "tombstones"}]
    assert missing == []


def test_identity_check_runs_after_the_unlock_payment_once_and_emits_an_event(env):
    from app.kyb import StubIdentityProvider
    from app.service import run_identity_check
    email = uniq()
    org = env.onboard(email, **SME)["id"]
    headers, _ = env.ctx_headers(email)
    assert env.client.get("/v1/organizations/current", headers=headers).json()["kyc_status"] == "NONE"
    event = {"id": str(uuid.uuid4()), "data": {"org_id": org, "application_id": str(uuid.uuid4()), "payment_id": str(uuid.uuid4())}}
    for _ in range(2):  # the same payment event delivered twice
        with env.db.system() as s:
            run_identity_check(s, StubIdentityProvider(), event)
    assert env.client.get("/v1/organizations/current", headers=headers).json()["kyc_status"] == "VERIFIED"
    with env.db.system() as s:
        n = s.execute(text("select count(*) from outbox where event_type like '%kyc_completed%' and org_id = :o"), {"o": org}).scalar()
    assert n == 1


def test_identity_check_rejects_a_company_without_a_valid_uid(env):
    from app.kyb import StubIdentityProvider
    assert StubIdentityProvider().verify_identity("x", "No UID AG", None) == "REJECTED"


# ===================================================================================== local passwords
def login(env, email, password):
    return env.client.post("/v1/auth/login", json={"email": email, "password": password})


def test_a_company_signs_up_with_a_password_and_can_log_in(env):
    email = uniq()
    env.onboard(email, password="correct horse battery", **SME)
    r = login(env, email.upper(), "correct horse battery")  # email is case-insensitive
    assert r.status_code == 200 and r.json()["email"] == email.lower()
    with env.db.system() as s:
        stored = s.execute(text("select c.password_hash from credentials c join users u on u.id = c.user_id where u.email = :e"), {"e": email.lower()}).scalar()
    assert stored.startswith("scrypt$") and "correct horse" not in stored  # only a salted hash is stored


def test_wrong_password_and_unknown_email_look_the_same(env):
    email = uniq()
    env.onboard(email, password="correct horse battery", **SME)
    wrong, unknown = login(env, email, "not the password"), login(env, uniq(), "whatever it is")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["code"] == unknown.json()["code"] == "invalid_credentials" and wrong.json()["detail"] == unknown.json()["detail"]


def test_five_failures_lock_the_account_for_fifteen_minutes(env):
    email = uniq()
    env.onboard(email, password="correct horse battery", **SME)
    for _ in range(5):
        assert login(env, email, "nope nope nope").status_code == 401
    locked = login(env, email, "correct horse battery")  # even the right password is refused while locked
    assert locked.status_code == 429 and locked.json()["code"] == "too_many_attempts"
    with env.db.system() as s:  # time passes
        s.execute(text("update credentials set locked_until = now() - interval '1 minute' where user_id = (select id from users where email = :e)"), {"e": email.lower()})
    assert login(env, email, "correct horse battery").status_code == 200
    assert login(env, email, "nope nope nope").status_code == 401  # the counter was reset by the successful login
    with env.db.system() as s:
        assert s.execute(text("select failed_attempts from credentials where user_id = (select id from users where email = :e)"), {"e": email.lower()}).scalar() == 1


def test_sign_up_rejects_weak_passwords_and_never_takes_over_an_existing_email(env):
    email = uniq()
    assert env.client.post("/v1/organizations", json={**SME, "password": "short"}, headers=env.user(email)).status_code == 422
    env.onboard(email, password="correct horse battery", **SME)
    again = env.client.post("/v1/organizations", json={**SME, "password": "another long password"}, headers=env.user(email))
    assert again.status_code == 409 and again.json()["code"] == "email_taken"
    assert login(env, email, "another long password").status_code == 401  # the original password still rules


def test_accounts_without_a_password_cannot_log_in_with_one(env):
    email = uniq()
    env.onboard(email, **SME)  # created without a password, like the seeded demo accounts
    assert login(env, email, "anything at all").status_code == 401
    with env.db.system() as s:
        assert s.execute(text("select count(*) from credentials c join users u on u.id = c.user_id where u.email = :e"), {"e": email.lower()}).scalar() == 0


def test_lender_and_accountant_sign_up_with_a_password_and_wait_for_verification(env):
    lender, accountant = uniq(), uniq()
    assert env.onboard(lender, type="LENDER", legal_name="Regionalbank AG", uid="CHE-111.222.333", password="correct horse battery")["kyb_status"] == "PENDING"
    assert env.onboard(accountant, type="FIDUCIARY", legal_name="Treuhand AG", uid="CHE-444.555.666", password="correct horse battery")["kyb_status"] == "PENDING"
    assert login(env, lender, "correct horse battery").status_code == 200 and login(env, accountant, "correct horse battery").status_code == 200
