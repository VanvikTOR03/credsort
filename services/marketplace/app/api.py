from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, Field

from credsort_common.db import Database
from credsort_common.errors import Forbidden
from credsort_common.money import DecimalStr
from credsort_common.security import AccessContext, Security

from . import apps, lending
from .domain import fields as F

Idem = Annotated[str | None, Header()]


class ApplicationCreate(BaseModel):
    amount: DecimalStr = Field(gt=0)
    term_months: int = Field(ge=6, le=120)
    purpose: str | None = Field(default=None, max_length=300)
    collateral: str | None = Field(default=None, max_length=300)
    assessment_id: uuid.UUID | None = None


class ApplicationUpdate(BaseModel):
    amount: DecimalStr | None = Field(default=None, gt=0)
    term_months: int | None = Field(default=None, ge=6, le=120)
    purpose: str | None = Field(default=None, max_length=300)
    collateral: str | None = Field(default=None, max_length=300)
    assessment_id: uuid.UUID | None = None


class Publication(BaseModel):
    fields: list[str]
    lender_org_ids: list[uuid.UUID] | None = None
    assessment_id: uuid.UUID | None = None


class CriteriaIn(BaseModel):
    criteria: dict[str, Any]


class AccessRequestIn(BaseModel):
    fields: list[str]


class OfferIn(BaseModel):
    amount: DecimalStr = Field(gt=0)
    rate: DecimalStr = Field(ge=0, le=30)
    term_months: int = Field(ge=1, le=360)
    fees: DecimalStr = Field(default=Decimal(0), ge=0)
    repayment: Literal["BULLET", "LINEAR", "ANNUITY"]
    collateral: str | None = Field(default=None, max_length=300)
    valid_until: dt.date


def build_router(db: Database, sec: Security, intel, billing, quotes) -> APIRouter:
    r = APIRouter()
    ctx_dep = sec.context_dependency()

    # ---------------------------------------------------------------- shared
    @r.get("/v1/field-catalogue")
    def catalogue(ctx: AccessContext = Depends(ctx_dep)):
        return {"fields": [{"field": f, "label": l, "owner": "marketplace" if f in F.MARKETPLACE_FIELDS else "intelligence", "default": f in F.SUMMARY_DEFAULT}
                           for f, l in F.CATALOGUE.items()]}

    @r.get("/v1/benchmark")
    def benchmark(ctx: AccessContext = Depends(ctx_dep)):
        return lending.benchmark(db)

    # ---------------------------------------------------------------- SME
    @r.post("/v1/applications", status_code=201)
    def create(body: ApplicationCreate, ctx: AccessContext = Depends(ctx_dep)):
        return apps.create_application(db, ctx, body.amount, body.term_months, body.purpose, body.collateral, body.assessment_id)

    @r.get("/v1/applications")
    def list_(ctx: AccessContext = Depends(ctx_dep)):
        return apps.list_applications(db, ctx)

    @r.get("/v1/applications/{app_id}")
    def get(app_id: uuid.UUID, ctx: AccessContext = Depends(ctx_dep)):
        return apps.get_application(db, ctx, app_id)

    @r.patch("/v1/applications/{app_id}")
    def update(app_id: uuid.UUID, body: ApplicationUpdate, ctx: AccessContext = Depends(ctx_dep)):
        return apps.update_application(db, ctx, app_id, body.model_dump(exclude_none=True))

    @r.get("/v1/applications/{app_id}/publication-preview")
    def preview(app_id: uuid.UUID, fields: Annotated[str, Query()], ctx: AccessContext = Depends(ctx_dep)):
        return apps.publication_preview(db, intel, ctx, app_id, [f for f in fields.split(",") if f])

    @r.post("/v1/applications/{app_id}/publication", status_code=201)
    def publish(app_id: uuid.UUID, body: Publication, response: Response, ctx: AccessContext = Depends(ctx_dep), idempotency_key: Idem = None):
        status, result = apps.publish(db, intel, ctx, app_id, body.fields, body.lender_org_ids, body.assessment_id, idempotency_key)
        response.status_code = status
        return result

    @r.post("/v1/applications/{app_id}/withdraw")
    def withdraw(app_id: uuid.UUID, ctx: AccessContext = Depends(ctx_dep)):
        return apps.withdraw(db, ctx, app_id)

    @r.get("/v1/applications/{app_id}/offers")
    def offers(app_id: uuid.UUID, sort: Literal["total_cost", "rate", "amount"] = "total_cost", ctx: AccessContext = Depends(ctx_dep)):
        return lending.sme_offers(db, ctx, app_id, sort)

    @r.post("/v1/offers/{offer_id}/selection")
    def select(offer_id: uuid.UUID, response: Response, ctx: AccessContext = Depends(ctx_dep), idempotency_key: Idem = None):
        status, result = lending.select_offer(db, quotes, ctx, offer_id, idempotency_key)
        response.status_code = status
        return result

    @r.post("/v1/applications/{app_id}/dispute")
    def dispute(app_id: uuid.UUID, ctx: AccessContext = Depends(ctx_dep)):
        return apps.dispute(db, ctx, app_id)

    @r.get("/v1/access-requests")
    def access_requests(application_id: uuid.UUID | None = None, ctx: AccessContext = Depends(ctx_dep)):
        return apps.list_access_requests(db, ctx, application_id)

    @r.post("/v1/access-requests/{request_id}/approve")
    def approve(request_id: uuid.UUID, ctx: AccessContext = Depends(ctx_dep)):
        return apps.decide_access_request(db, intel, ctx, request_id, True)

    @r.post("/v1/access-requests/{request_id}/deny")
    def deny(request_id: uuid.UUID, ctx: AccessContext = Depends(ctx_dep)):
        return apps.decide_access_request(db, intel, ctx, request_id, False)

    @r.get("/v1/disclosures")
    def disclosures(ctx: AccessContext = Depends(ctx_dep)):
        return apps.list_disclosures(db, ctx)

    @r.post("/v1/disclosures/revoke-all")
    def revoke_all(ctx: AccessContext = Depends(ctx_dep)):
        return apps.revoke_all(db, ctx)

    @r.post("/v1/disclosures/{disclosure_id}/revoke")
    def revoke(disclosure_id: uuid.UUID, ctx: AccessContext = Depends(ctx_dep)):
        return apps.revoke_disclosure(db, ctx, disclosure_id)

    # ---------------------------------------------------------------- lender
    @r.get("/v1/lender/criteria")
    def get_criteria(ctx: AccessContext = Depends(ctx_dep)):
        return lending.get_criteria(db, ctx)

    @r.put("/v1/lender/criteria")
    def put_criteria(body: CriteriaIn, ctx: AccessContext = Depends(ctx_dep)):
        return lending.save_criteria(db, ctx, body.criteria)

    @r.get("/v1/lender/matches")
    def matches(ctx: AccessContext = Depends(ctx_dep)):
        return lending.matches(db, ctx)

    @r.get("/v1/lender/applications/{app_id}")
    def lender_app(app_id: uuid.UUID, ctx: AccessContext = Depends(ctx_dep)):
        return lending.lender_application(db, ctx, app_id)

    @r.post("/v1/lender/applications/{app_id}/access-requests", status_code=201)
    def request_access(app_id: uuid.UUID, body: AccessRequestIn, ctx: AccessContext = Depends(ctx_dep)):
        return lending.request_access(db, ctx, app_id, body.fields)

    @r.post("/v1/lender/applications/{app_id}/offers", status_code=201)
    def submit(app_id: uuid.UUID, body: OfferIn, response: Response, ctx: AccessContext = Depends(ctx_dep), idempotency_key: Idem = None):
        status, result = lending.submit_offer(db, billing, ctx, app_id, body.model_dump(), idempotency_key)
        response.status_code = status
        return result

    @r.get("/v1/lender/offers")
    def lender_offers(ctx: AccessContext = Depends(ctx_dep)):
        return lending.lender_offers(db, ctx)

    @r.post("/v1/lender/offers/{offer_id}/withdraw")
    def withdraw_offer(offer_id: uuid.UUID, ctx: AccessContext = Depends(ctx_dep)):
        return lending.withdraw_offer(db, ctx, offer_id)

    @r.post("/v1/lender/offers/{offer_id}/confirm-payout")
    def confirm_payout(offer_id: uuid.UUID, response: Response, ctx: AccessContext = Depends(ctx_dep), idempotency_key: Idem = None):
        status, result = lending.confirm_payout(db, ctx, offer_id, idempotency_key)
        response.status_code = status
        return result

    @r.post("/v1/lender/offers/{offer_id}/cancel-loan")
    def cancel_loan(offer_id: uuid.UUID, ctx: AccessContext = Depends(ctx_dep)):
        return lending.cancel_loan(db, ctx, offer_id)

    return r
