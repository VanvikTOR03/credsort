"""Identity use cases: onboarding, context tokens, members, delegation, admin (ADR-0002, ADR-0019, ADR-0020, ADR-0027)."""
from __future__ import annotations

import secrets
import uuid

from sqlalchemy import text

from credsort_common.audit import record_audit
from credsort_common.db import Database
from credsort_common.errors import Conflict, Forbidden, NotFound, Unprocessable
from credsort_common.events import emit
from credsort_common.security import AccessContext, KeyStore, new_context_claims

from .kyb import KybProvider
from .usertoken import UserIdentity

SVC = "identity"
ROLE_BY_ORG_TYPE = {"SME": "SME_ADMIN", "LENDER": "LENDER_ADMIN", "FIDUCIARY": "FIDUCIARY_ADVISOR", "PLATFORM": "PLATFORM_ADMIN"}
ROLES_BY_ORG_TYPE = {"SME": {"SME_ADMIN", "SME_MEMBER"}, "LENDER": {"LENDER_ADMIN", "CREDIT_OFFICER"},
                     "FIDUCIARY": {"FIDUCIARY_ADVISOR"}, "PLATFORM": {"PLATFORM_ADMIN"}}
DELEGATION_SCOPES = {"VIEW_PROFILE", "PREPARE_APPLICATION"}  # never selection or disclosure (ADR-0019)
ADMIN_ROLES = ("SME_ADMIN", "LENDER_ADMIN", "FIDUCIARY_ADVISOR", "PLATFORM_ADMIN")


def _referral_code() -> str:
    return "CS-" + secrets.token_hex(3).upper()


def _find_user(s, who: UserIdentity):
    row = s.execute(text("select id, keycloak_sub, email, display_name from users where keycloak_sub = :s"), {"s": who.sub}).first()
    if row is None:
        row = s.execute(text("select id, keycloak_sub, email, display_name from users where email = :e"), {"e": who.email}).first()
        if row is not None and row.keycloak_sub is None:  # first login of a pre-created user: link the subject
            s.execute(text("update users set keycloak_sub = :s where id = :i"), {"s": who.sub, "i": row.id})
    return row


def _memberships(s, user_id):
    return s.execute(text(
        "select m.org_id, m.role, o.type, o.legal_name, o.kyb_status, o.status, o.industry, o.employees from memberships m "
        "join organizations o on o.id = m.org_id where m.user_id = :u and m.revoked_at is null order by m.created_at"), {"u": user_id}).all()


# --------------------------------------------------------------------------- sessions
def me(db: Database, who: UserIdentity) -> dict:
    with db.system() as s:
        user = _find_user(s, who)
        if user is None:
            return {"user": None, "memberships": [], "identity": {"email": who.email, "name": who.name}}
        return {"user": {"id": user.id, "email": user.email, "display_name": user.display_name},
                "memberships": [{"org_id": m.org_id, "org_name": m.legal_name, "org_type": m.type, "role": m.role,
                                 "kyb_status": m.kyb_status, "status": m.status} for m in _memberships(s, user.id)]}


def issue_context_token(db: Database, keystore: KeyStore, who: UserIdentity, org_id: uuid.UUID | None,
                        on_behalf_of: uuid.UUID | None) -> dict:
    with db.system() as s:
        user = _find_user(s, who)
        if user is None:
            raise NotFound("no account exists for this login; create an organization first", code="no_account")
        rows = [m for m in _memberships(s, user.id) if m.status == "ACTIVE"]
        if not rows:
            raise Forbidden("no active membership", code="no_membership")
        chosen = next((m for m in rows if org_id is None or m.org_id == org_id), None)
        if chosen is None:
            raise Forbidden("not a member of that organization", code="not_a_member")
        scopes: list[str] = []
        if on_behalf_of:
            if chosen.type != "FIDUCIARY":
                raise Forbidden("only fiduciaries can act on behalf of an SME", code="delegation_forbidden")
            d = s.execute(text("select d.scopes, o.status from delegations d join organizations o on o.id = d.sme_org_id "
                               "where d.sme_org_id = :b and d.fiduciary_org_id = :f and d.revoked_at is null"),
                          {"b": on_behalf_of, "f": chosen.org_id}).first()
            if d is None or d.status != "ACTIVE":
                raise Forbidden("no active delegation", code="no_delegation")
            scopes = list(d.scopes)
        claims = new_context_claims(user_id=user.id, org_id=chosen.org_id, org_type=chosen.type, org_name=chosen.legal_name,
                                    role=chosen.role, scopes=scopes, on_behalf_of=on_behalf_of, kyb_status=chosen.kyb_status,
                                    industry=chosen.industry, employees=chosen.employees)
        return {"token": keystore.sign(claims), "expires_in": claims["exp"] - claims["iat"],
                "org": {"id": chosen.org_id, "name": chosen.legal_name, "type": chosen.type, "role": chosen.role,
                        "kyb_status": chosen.kyb_status, "on_behalf_of": on_behalf_of, "scopes": scopes},
                "memberships": [{"org_id": m.org_id, "org_name": m.legal_name, "org_type": m.type, "role": m.role} for m in rows]}


# --------------------------------------------------------------------------- onboarding
def create_organization(db: Database, kyb: KybProvider, who: UserIdentity, *, org_type: str, legal_name: str, uid: str | None,
                        legal_form: str | None, industry: str | None, employees: int | None, referral_code: str | None) -> dict:
    if org_type == "PLATFORM":
        raise Forbidden("platform organizations are created by operators", code="org_type_forbidden")
    with db.system() as s:
        user = _find_user(s, who)
        if user is None:
            user_id = uuid.uuid4()
            s.execute(text("insert into users(id, keycloak_sub, email, display_name) values (:i, :s, :e, :n)"),
                      {"i": user_id, "s": who.sub, "e": who.email, "n": who.name})
        else:
            user_id = user.id
        referrer = None
        if referral_code:
            referrer = s.execute(text("select id from organizations where referral_code = :c and type = 'FIDUCIARY'"), {"c": referral_code}).first()
            if referrer is None:
                raise Unprocessable("unknown referral code", code="unknown_referral_code")
        org_id = uuid.uuid4()
        status = kyb.verify(org_type, uid, legal_name)
        s.execute(text("insert into organizations(id, type, legal_name, uid, legal_form, industry, employees, kyb_status, referred_by_org_id, referral_code) "
                       "values (:i, :t, :n, :u, :f, :ind, :emp, :k, :r, :c)"),
                  {"i": org_id, "t": org_type, "n": legal_name, "u": uid, "f": legal_form, "ind": industry, "emp": employees, "k": status,
                   "r": referrer.id if referrer else None, "c": _referral_code()})
        s.execute(text("insert into memberships(id, user_id, org_id, role) values (:i, :u, :o, :r)"),
                  {"i": uuid.uuid4(), "u": user_id, "o": org_id, "r": ROLE_BY_ORG_TYPE[org_type]})
        emit(s, SVC, "identity.organization.created", org_id, f"organization/{org_id}",
             {"org_id": org_id, "org_type": org_type, "referred_by_org_id": referrer.id if referrer else None})
        if status != "UNVERIFIED":
            emit(s, SVC, "identity.organization.verification_changed", org_id, f"organization/{org_id}", {"org_id": org_id, "kyb_status": status}, version=2)
        record_audit(s, SVC, None, "organization.created", f"organization/{org_id}", org_id=org_id, actor_user_id=user_id)
        return {"id": org_id, "type": org_type, "kyb_status": status}


def current_org(db: Database, ctx: AccessContext) -> dict:
    with db.session(ctx.org_id) as s:
        o = s.execute(text("select id, type, legal_name, uid, legal_form, industry, employees, kyb_status, status, referral_code, referred_by_org_id "
                           "from organizations where id = :i"), {"i": ctx.org_id}).first()
        if o is None:
            raise NotFound("organization not found")
        return dict(o._mapping)


def lookup_referral(db: Database, code: str) -> dict:
    with db.system() as s:
        o = s.execute(text("select id, legal_name from organizations where referral_code = :c and type = 'FIDUCIARY' and status = 'ACTIVE'"), {"c": code}).first()
    if o is None:
        raise NotFound("unknown referral code", code="unknown_referral_code")
    return {"id": o.id, "name": o.legal_name}


# --------------------------------------------------------------------------- members
def list_members(db: Database, ctx: AccessContext) -> list[dict]:
    with db.session(ctx.org_id) as s:
        rows = s.execute(text("select u.id as user_id, u.email, u.display_name, m.role, m.created_at from memberships m "
                              "join users u on u.id = m.user_id where m.org_id = :o and m.revoked_at is null order by m.created_at"), {"o": ctx.org_id}).all()
        return [dict(r._mapping) for r in rows]


def add_member(db: Database, ctx: AccessContext, email: str, display_name: str, role: str) -> dict:
    if role not in ROLES_BY_ORG_TYPE[ctx.org_type]:
        raise Unprocessable(f"role {role} does not exist for {ctx.org_type} organizations", code="invalid_role")
    with db.system() as s:
        user = s.execute(text("select id from users where email = :e"), {"e": email.lower()}).first()
        user_id = user.id if user else uuid.uuid4()
        if not user:
            s.execute(text("insert into users(id, email, display_name) values (:i, :e, :n)"), {"i": user_id, "e": email.lower(), "n": display_name})
        if s.execute(text("select 1 from memberships where user_id = :u and org_id = :o and revoked_at is null"), {"u": user_id, "o": ctx.org_id}).first():
            raise Conflict("already a member", code="already_member")
        s.execute(text("insert into memberships(id, user_id, org_id, role) values (:i, :u, :o, :r) "
                       "on conflict (user_id, org_id) do update set role = excluded.role, revoked_at = null"),
                  {"i": uuid.uuid4(), "u": user_id, "o": ctx.org_id, "r": role})
        record_audit(s, SVC, ctx, "member.added", f"user/{user_id}", org_id=ctx.org_id)
    return {"user_id": user_id, "email": email.lower(), "role": role}


def remove_member(db: Database, ctx: AccessContext, user_id: uuid.UUID) -> None:
    if user_id == ctx.user_id:
        raise Unprocessable("you cannot remove yourself", code="cannot_remove_self")
    with db.session(ctx.org_id) as s:
        updated = s.execute(text("update memberships set revoked_at = now() where user_id = :u and org_id = :o and revoked_at is null returning revoked_at"),
                            {"u": user_id, "o": ctx.org_id}).first()
        if not updated:
            raise NotFound("member not found")
        emit(s, SVC, "identity.membership.revoked", ctx.org_id, f"membership/{user_id}", {"org_id": ctx.org_id, "user_id": user_id, "revoked_at": updated.revoked_at})
        record_audit(s, SVC, ctx, "member.removed", f"user/{user_id}", org_id=ctx.org_id)


# --------------------------------------------------------------------------- delegation
def grant_delegation(db: Database, ctx: AccessContext, fiduciary_org_id: uuid.UUID | None, referral_code: str | None, scopes: list[str]) -> dict:
    bad = set(scopes) - DELEGATION_SCOPES
    if bad or not scopes:
        raise Unprocessable(f"scopes must be a non-empty subset of {sorted(DELEGATION_SCOPES)}", code="invalid_scopes")
    with db.system() as s:  # the fiduciary row belongs to another tenant: resolved by the platform, never exposed
        fid = s.execute(text("select id, legal_name, status, kyb_status from organizations where type = 'FIDUCIARY' and "
                             "(id = :i or referral_code = :c)"), {"i": fiduciary_org_id, "c": referral_code}).first()
        if fid is None or fid.status != "ACTIVE":
            raise NotFound("fiduciary not found", code="fiduciary_not_found")
        if s.execute(text("select 1 from delegations where sme_org_id = :s and fiduciary_org_id = :f and revoked_at is null"), {"s": ctx.org_id, "f": fid.id}).first():
            raise Conflict("delegation already active", code="delegation_exists")
        did = uuid.uuid4()
        s.execute(text("insert into delegations(id, sme_org_id, fiduciary_org_id, scopes, granted_by) values (:i, :s, :f, :sc, :u)"),
                  {"i": did, "s": ctx.org_id, "f": fid.id, "sc": scopes, "u": ctx.user_id})
        emit(s, SVC, "identity.delegation.granted", ctx.org_id, f"delegation/{did}", {"sme_org_id": ctx.org_id, "fiduciary_org_id": fid.id, "scopes": scopes})
        record_audit(s, SVC, ctx, "delegation.granted", f"delegation/{did}", org_id=ctx.org_id)
        return {"id": did, "fiduciary_org_id": fid.id, "fiduciary_name": fid.legal_name, "scopes": scopes}


def list_delegations(db: Database, ctx: AccessContext) -> list[dict]:
    # Both parties of a delegation may see each other's name. The counterparty row is hidden by RLS from the caller, so this
    # narrowly scoped query runs as SYSTEM and filters on the caller's own organization explicitly.
    with db.system() as s:
        rows = s.execute(text("select d.id, d.sme_org_id, d.fiduciary_org_id, d.scopes, d.granted_at, s.legal_name as sme_name, f.legal_name as fiduciary_name "
                              "from delegations d join organizations s on s.id = d.sme_org_id join organizations f on f.id = d.fiduciary_org_id "
                              "where d.revoked_at is null and (d.sme_org_id = :o or d.fiduciary_org_id = :o)"), {"o": ctx.org_id}).all()
    return [dict(r._mapping) for r in rows]


def revoke_delegation(db: Database, ctx: AccessContext, delegation_id: uuid.UUID) -> None:
    with db.session(ctx.org_id) as s:
        d = s.execute(text("update delegations set revoked_at = now() where id = :i and sme_org_id = :o and revoked_at is null "
                           "returning fiduciary_org_id"), {"i": delegation_id, "o": ctx.org_id}).first()
        if not d:
            raise NotFound("delegation not found")
        emit(s, SVC, "identity.delegation.revoked", ctx.org_id, f"delegation/{delegation_id}", {"sme_org_id": ctx.org_id, "fiduciary_org_id": d.fiduciary_org_id})
        record_audit(s, SVC, ctx, "delegation.revoked", f"delegation/{delegation_id}", org_id=ctx.org_id)


# --------------------------------------------------------------------------- platform admin
def admin_list(db: Database, status: str | None) -> list[dict]:
    with db.session(None, "PLATFORM") as s:
        rows = s.execute(text("select id, type, legal_name, uid, industry, employees, kyb_status, status, created_at from organizations "
                              "where type <> 'PLATFORM' and (cast(:k as text) is null or kyb_status = cast(:k as text)) order by created_at desc"), {"k": status}).all()
    return [dict(r._mapping) for r in rows]


def admin_set_kyb(db: Database, ctx: AccessContext, org_id: uuid.UUID, new_status: str) -> dict:
    with db.session(None, "PLATFORM") as s:
        row = s.execute(text("update organizations set kyb_status = :k where id = :i and type <> 'PLATFORM' returning id"), {"k": new_status, "i": org_id}).first()
        if not row:
            raise NotFound("organization not found")
        emit(s, SVC, "identity.organization.verification_changed", org_id, f"organization/{org_id}", {"org_id": org_id, "kyb_status": new_status}, version=3)
        record_audit(s, SVC, ctx, f"organization.kyb.{new_status.lower()}", f"organization/{org_id}", org_id=org_id)
    return {"id": org_id, "kyb_status": new_status}


def admin_suspend(db: Database, ctx: AccessContext, org_id: uuid.UUID) -> dict:
    with db.session(None, "PLATFORM") as s:
        row = s.execute(text("update organizations set status = 'SUSPENDED' where id = :i and type <> 'PLATFORM' returning id"), {"i": org_id}).first()
        if not row:
            raise NotFound("organization not found")
        emit(s, SVC, "identity.organization.suspended", org_id, f"organization/{org_id}", {"org_id": org_id})
        record_audit(s, SVC, ctx, "organization.suspended", f"organization/{org_id}", org_id=org_id)
    return {"id": org_id, "status": "SUSPENDED"}


def request_deletion(db: Database, ctx: AccessContext, org_id: uuid.UUID) -> dict:
    """Coordinates deletion across services (ADR-0031). Identity closes the request when every service confirmed."""
    with db.system() as s:
        if s.execute(text("select 1 from deletion_requests where org_id = :o"), {"o": org_id}).first():
            raise Conflict("deletion already requested", code="deletion_exists")
        req = s.execute(text("insert into deletion_requests(org_id) values (:o) returning requested_at"), {"o": org_id}).first()
        s.execute(text("update organizations set status = 'SUSPENDED' where id = :o"), {"o": org_id})
        emit(s, SVC, "identity.organization.suspended", org_id, f"organization/{org_id}", {"org_id": org_id}, version=2)
        emit(s, SVC, "identity.organization.deletion_requested", org_id, f"organization/{org_id}", {"org_id": org_id, "requested_at": req.requested_at})
        record_audit(s, SVC, ctx, "organization.deletion_requested", f"organization/{org_id}", org_id=org_id)
    return {"org_id": org_id, "requested_at": req.requested_at}


DELETING_SERVICES = ("accounting", "intelligence", "marketplace", "billing", "advisory", "notification", "audit")


def deletion_status(db: Database, org_id: uuid.UUID) -> dict | None:
    with db.system() as s:
        r = s.execute(text("select requested_at, confirmations, closed_at from deletion_requests where org_id = :o"), {"o": org_id}).first()
    if not r:
        return None
    return {"requested_at": r.requested_at, "confirmations": r.confirmations, "closed_at": r.closed_at,
            "pending": [x for x in DELETING_SERVICES if x not in r.confirmations]}


def confirm_deletion(s, org_id: uuid.UUID, service: str) -> None:
    """Called by the audit-event consumer when a service records `data.deleted` (ADR-0031)."""
    row = s.execute(text("update deletion_requests set confirmations = confirmations || cast(:c as jsonb) where org_id = :o and closed_at is null "
                         "returning confirmations"), {"c": '{"%s": true}' % service, "o": org_id}).first()
    if row and all(x in row.confirmations for x in DELETING_SERVICES):
        s.execute(text("update deletion_requests set closed_at = now() where org_id = :o"), {"o": org_id})
        s.execute(text("update organizations set status = 'DELETED', legal_name = 'deleted', uid = null where id = :o"), {"o": org_id})
        s.execute(text("update memberships set revoked_at = coalesce(revoked_at, now()) where org_id = :o"), {"o": org_id})
