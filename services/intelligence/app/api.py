from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from credsort_common.db import Database
from credsort_common.security import AccessContext, Security, require_sme_access

from . import service as svc


class ScenarioInputs(BaseModel):
    debt_repayment_from_cash: str | None = Field(default=None, pattern=r"^\d+(\.\d{1,2})?$")
    revenue_change_pct: str | None = Field(default=None, pattern=r"^-?\d+(\.\d{1,2})?$")
    cost_reduction_pct: str | None = Field(default=None, pattern=r"^\d+(\.\d{1,2})?$")


class ScenarioCreate(BaseModel):
    assessment_id: uuid.UUID
    inputs: ScenarioInputs


def build_router(db: Database, sec: Security, billing) -> APIRouter:
    r = APIRouter()
    ctx_dep = sec.context_dependency()
    marketplace_only = sec.service_dependency({"marketplace"})
    advisory_only = sec.service_dependency({"advisory"})

    def viewer(ctx: AccessContext = Depends(ctx_dep)) -> AccessContext:
        require_sme_access(ctx, "VIEW_PROFILE")
        return ctx

    @r.get("/v1/profile/current")
    def current(ctx: AccessContext = Depends(viewer)):
        return svc.current_profile(db, ctx)

    @r.get("/v1/assessments")
    def assessments(ctx: AccessContext = Depends(viewer)):
        return svc.list_assessments(db, ctx)

    @r.get("/v1/assessments/{assessment_id}")
    def assessment(assessment_id: uuid.UUID, ctx: AccessContext = Depends(viewer)):
        return svc.get_assessment(db, ctx, assessment_id)

    @r.get("/v1/field-catalogue")
    def catalogue(ctx: AccessContext = Depends(viewer)):
        return {"fields": svc.FIELD_CATALOGUE}

    @r.post("/v1/scenarios", status_code=201)
    def scenario(body: ScenarioCreate, ctx: AccessContext = Depends(viewer)):
        inputs = {k: v for k, v in body.inputs.model_dump().items() if v is not None}
        return svc.run_scenario(db, billing, ctx, body.assessment_id, inputs)

    # ---- internal: both a service token from the allowed caller AND the user's context token are required ----
    @r.get("/internal/v1/assessments/{assessment_id}/profile-extract")
    def profile_extract(assessment_id: uuid.UUID, fields: Annotated[str, Query()], ctx: AccessContext = Depends(viewer),
                        caller: str = Depends(marketplace_only)):
        return svc.profile_extract(db, ctx, assessment_id, [f for f in fields.split(",") if f])

    @r.get("/internal/v1/assessments/{assessment_id}/advisory-context")
    def advisory_context(assessment_id: uuid.UUID, scenario_id: uuid.UUID | None = None, ctx: AccessContext = Depends(viewer),
                         caller: str = Depends(advisory_only)):
        return svc.advisory_context(db, ctx, assessment_id, scenario_id)

    return r
