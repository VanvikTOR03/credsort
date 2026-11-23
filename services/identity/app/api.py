from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from credsort_common.db import Database
from credsort_common.errors import Unauthorized
from credsort_common.security import AccessContext, KeyStore, Security, forbid_delegated, require_role

from . import service as svc
from .kyb import KybProvider
from .usertoken import UserIdentity


class TokenRequest(BaseModel):
    org_id: uuid.UUID | None = None
    on_behalf_of: uuid.UUID | None = None


class OrgCreate(BaseModel):
    type: Literal["SME", "LENDER", "FIDUCIARY"]
    legal_name: str = Field(min_length=2, max_length=200)
    uid: str | None = Field(default=None, pattern=r"^CHE-\d{3}\.\d{3}\.\d{3}$")
    legal_form: Literal["AG", "GmbH", "Other"] | None = None
    industry: str | None = Field(default=None, max_length=60)
    employees: int | None = Field(default=None, ge=0, le=100000)
    canton: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    referral_code: str | None = None
    password: str | None = Field(default=None, min_length=10, max_length=128)  # local password; never logged or returned


class PasswordLogin(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=128)


class MemberAdd(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    display_name: str = Field(min_length=1, max_length=120)
    role: str


class DelegationCreate(BaseModel):
    fiduciary_org_id: uuid.UUID | None = None
    referral_code: str | None = None
    scopes: list[str] = ["VIEW_PROFILE", "PREPARE_APPLICATION"]


def build_router(db: Database, sec: Security, keystore: KeyStore, kyb: KybProvider, user_verifier) -> APIRouter:
    r = APIRouter()
    ctx_dep = sec.context_dependency()

    def user_identity(authorization: Annotated[str | None, Header()] = None) -> UserIdentity:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise Unauthorized("missing bearer user token")
        return user_verifier.verify(authorization.split(" ", 1)[1].strip())

    @r.get("/.well-known/jwks.json", include_in_schema=False)
    def jwks():
        return keystore.jwks()

    # ---- public, called by the BFF before any session exists (rate-limited at the edge) ----
    @r.post("/v1/auth/login")
    def password_login(body: PasswordLogin):
        return svc.password_login(db, body.email, body.password)

    # ---- user-token endpoints (called by the BFF) ----
    @r.get("/v1/me")
    def me(who: UserIdentity = Depends(user_identity)):
        return svc.me(db, who)

    @r.post("/v1/context-tokens")
    def context_token(body: TokenRequest, who: UserIdentity = Depends(user_identity)):
        return svc.issue_context_token(db, keystore, who, body.org_id, body.on_behalf_of)

    @r.post("/v1/organizations", status_code=201)
    def create_org(body: OrgCreate, who: UserIdentity = Depends(user_identity)):
        return svc.create_organization(db, kyb, who, org_type=body.type, legal_name=body.legal_name, uid=body.uid, legal_form=body.legal_form,
                                       industry=body.industry, employees=body.employees, canton=body.canton, referral_code=body.referral_code, password=body.password)

    # ---- context-token endpoints ----
    @r.get("/v1/organizations/current")
    def current(ctx: AccessContext = Depends(ctx_dep)):
        return svc.current_org(db, ctx)

    @r.get("/v1/public/referrals/{code}")
    def public_referral(code: str):
        """Before sign-up: the name of the fiduciary an invitation code belongs to (nothing else). Rate-limited at the edge."""
        return {"name": svc.lookup_referral(db, code)["name"]}

    @r.get("/v1/referrals/{code}")
    def referral(code: str, ctx: AccessContext = Depends(ctx_dep)):
        return svc.lookup_referral(db, code)

    @r.get("/v1/members")
    def members(ctx: AccessContext = Depends(ctx_dep)):
        return svc.list_members(db, ctx)

    @r.post("/v1/members", status_code=201)
    def add_member(body: MemberAdd, ctx: AccessContext = Depends(ctx_dep)):
        require_role(ctx, *svc.ADMIN_ROLES)
        forbid_delegated(ctx)
        return svc.add_member(db, ctx, body.email, body.display_name, body.role)

    @r.delete("/v1/members/{user_id}", status_code=204)
    def remove_member(user_id: uuid.UUID, ctx: AccessContext = Depends(ctx_dep)):
        require_role(ctx, *svc.ADMIN_ROLES)
        forbid_delegated(ctx)
        svc.remove_member(db, ctx, user_id)

    @r.get("/v1/delegations")
    def delegations(ctx: AccessContext = Depends(ctx_dep)):
        return svc.list_delegations(db, ctx)

    @r.post("/v1/delegations", status_code=201)
    def grant(body: DelegationCreate, ctx: AccessContext = Depends(ctx_dep)):
        require_role(ctx, "SME_ADMIN")
        forbid_delegated(ctx)
        return svc.grant_delegation(db, ctx, body.fiduciary_org_id, body.referral_code, body.scopes)

    @r.delete("/v1/delegations/{delegation_id}", status_code=204)
    def revoke(delegation_id: uuid.UUID, ctx: AccessContext = Depends(ctx_dep)):
        require_role(ctx, "SME_ADMIN")
        forbid_delegated(ctx)
        svc.revoke_delegation(db, ctx, delegation_id)

    @r.get("/v1/fiduciary/clients")
    def clients(ctx: AccessContext = Depends(ctx_dep)):
        require_role(ctx, "FIDUCIARY_ADVISOR")
        return [d for d in svc.list_delegations(db, ctx) if d["fiduciary_org_id"] == ctx.org_id]

    @r.post("/v1/organizations/current/deletion-request", status_code=202)
    def deletion(ctx: AccessContext = Depends(ctx_dep)):
        require_role(ctx, "SME_ADMIN", "LENDER_ADMIN", "FIDUCIARY_ADVISOR")
        forbid_delegated(ctx)
        return svc.request_deletion(db, ctx, ctx.org_id)

    @r.get("/v1/organizations/current/deletion-request")
    def deletion_status(ctx: AccessContext = Depends(ctx_dep)):
        return svc.deletion_status(db, ctx.org_id) or {}

    # ---- platform admin ----
    def admin(ctx: AccessContext = Depends(ctx_dep)) -> AccessContext:
        require_role(ctx, "PLATFORM_ADMIN")
        return ctx

    @r.get("/v1/admin/organizations")
    def admin_orgs(kyb_status: str | None = None, ctx: AccessContext = Depends(admin)):
        return svc.admin_list(db, kyb_status)

    @r.post("/v1/admin/organizations/{org_id}/verify")
    def verify(org_id: uuid.UUID, ctx: AccessContext = Depends(admin)):
        return svc.admin_set_kyb(db, ctx, org_id, "VERIFIED")

    @r.post("/v1/admin/organizations/{org_id}/reject")
    def reject(org_id: uuid.UUID, ctx: AccessContext = Depends(admin)):
        return svc.admin_set_kyb(db, ctx, org_id, "REJECTED")

    @r.post("/v1/admin/organizations/{org_id}/suspend")
    def suspend(org_id: uuid.UUID, ctx: AccessContext = Depends(admin)):
        return svc.admin_suspend(db, ctx, org_id)

    return r
