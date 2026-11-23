from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from credsort_common.db import Database
from credsort_common.errors import Forbidden, NotFound
from credsort_common.money import DecimalStr
from credsort_common.security import AccessContext, KeyStore, Security, require_role

from . import service as svc


class QuoteRequest(BaseModel):
    action: Literal["LOAN_FUNDED"]
    subject_id: uuid.UUID
    payer_org_id: uuid.UUID
    payer_type: Literal["SME", "LENDER"]
    basis: DecimalStr


class RuleIn(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    payer: Literal["SME", "LENDER"]
    trigger: Literal["LOAN_FUNDED", "OFFERS_UNLOCKED", "MANUAL"] = "LOAN_FUNDED"
    calculator: Literal["FIXED", "PERCENT_OF_PRINCIPAL"]
    amount: DecimalStr | None = None
    percent: DecimalStr | None = None
    min_amount: DecimalStr | None = None
    cap_amount: DecimalStr | None = None


class BookCreate(BaseModel):
    rules: list[RuleIn]
    placeholder: bool = False


class UnlockPay(BaseModel):
    application_id: uuid.UUID
    method: Literal["TWINT", "VISA", "MASTERCARD"]


class Activate(BaseModel):
    effective_from: dt.date | None = None


class EntitlementSet(BaseModel):
    org_id: uuid.UUID
    entitlements: list[str]


def build_router(db: Database, sec: Security, keystore: KeyStore, gateway) -> APIRouter:
    r = APIRouter()
    ctx_dep = sec.context_dependency()
    marketplace_only = sec.service_dependency({"marketplace"})
    entitlement_readers = sec.service_dependency({"intelligence", "advisory"})

    @r.get("/.well-known/jwks.json", include_in_schema=False)
    def jwks():
        return keystore.jwks()

    # ---- internal ----
    @r.post("/internal/v1/quotes", status_code=201)
    def quote(body: QuoteRequest, caller: str = Depends(marketplace_only)):
        return svc.issue_quote(db, keystore, action=body.action, subject_id=body.subject_id, payer_org_id=body.payer_org_id,
                               payer_type=body.payer_type, basis=body.basis)

    @r.get("/internal/v1/organizations/{org_id}/entitlements")
    def entitlements(org_id: uuid.UUID, ctx: AccessContext = Depends(ctx_dep), caller: str = Depends(entitlement_readers)):
        if ctx.effective_org_id != org_id:
            raise NotFound("organization not found")
        return {"entitlements": svc.entitlements(db, org_id)}

    # ---- external ----
    @r.get("/v1/pricing")
    def pricing(ctx: AccessContext = Depends(ctx_dep)):
        return svc.public_pricing(db)

    @r.get("/v1/unlock/price")
    def unlock_price(ctx: AccessContext = Depends(ctx_dep)):
        return svc.unlock_price(db)

    @r.post("/v1/unlock/payments", status_code=201)
    def pay_unlock(body: UnlockPay, ctx: AccessContext = Depends(ctx_dep)):
        return svc.pay_unlock(db, gateway, ctx, body.application_id, body.method)

    @r.get("/v1/unlock/payments")
    def unlock_payments(ctx: AccessContext = Depends(ctx_dep)):
        return svc.list_unlock_payments(db, ctx)

    @r.get("/v1/charges")
    def charges(ctx: AccessContext = Depends(ctx_dep)):
        return svc.list_charges(db, ctx)

    def admin(ctx: AccessContext = Depends(ctx_dep)) -> AccessContext:
        require_role(ctx, "PLATFORM_ADMIN")
        return ctx

    @r.get("/v1/admin/price-books")
    def books(ctx: AccessContext = Depends(admin)):
        return svc.list_price_books(db)

    @r.post("/v1/admin/price-books", status_code=201)
    def create_book(body: BookCreate, ctx: AccessContext = Depends(admin)):
        return svc.create_price_book(db, ctx, [x.model_dump() for x in body.rules], body.placeholder)

    @r.post("/v1/admin/price-books/{book_id}/activate")
    def activate(book_id: uuid.UUID, body: Activate, ctx: AccessContext = Depends(admin)):
        return svc.activate_price_book(db, ctx, book_id, body.effective_from)

    @r.get("/v1/admin/charges")
    def admin_charges(status: str | None = None, ctx: AccessContext = Depends(admin)):
        return svc.admin_charges(db, status)

    @r.post("/v1/admin/charges/{charge_id}/release")
    def release(charge_id: uuid.UUID, ctx: AccessContext = Depends(admin)):
        return svc.admin_resolve(db, ctx, charge_id, "release")

    @r.post("/v1/admin/charges/{charge_id}/waive")
    def waive(charge_id: uuid.UUID, ctx: AccessContext = Depends(admin)):
        return svc.admin_resolve(db, ctx, charge_id, "waive")

    @r.post("/v1/admin/entitlements")
    def set_entitlements(body: EntitlementSet, ctx: AccessContext = Depends(admin)):
        return svc.set_entitlements(db, ctx, body.org_id, body.entitlements)

    return r
