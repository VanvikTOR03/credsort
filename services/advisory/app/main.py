from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from typing import Literal

from pydantic import BaseModel, Field

from credsort_common.app import create_app
from credsort_common.background import Consumer
from credsort_common.config import Settings
from credsort_common.db import Database
from credsort_common.errors import Unprocessable
from credsort_common.security import AccessContext, Security, require_sme_access
from credsort_common.upstream import UpstreamClient

from . import service as svc
from .plugins.models import LanguageModel, build_chain

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


class ScenarioExplain(BaseModel):
    assessment_id: uuid.UUID


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=600)


class ChatIn(BaseModel):
    assessment_id: uuid.UUID
    messages: list[ChatMessage] = Field(min_length=1, max_length=12)


def create_service_app(settings: Settings | None = None, db: Database | None = None, security: Security | None = None, intelligence=None, billing=None,
                       chain: list[LanguageModel] | None = None):
    consumers = [Consumer("advisory-entitlements", ["billing.entitlements.changed.*"], svc.upsert_entitlements),
                 Consumer("advisory-deletion", ["identity.organization.deletion_requested.*"], lambda s, e: svc.delete_org_data(s, e["credsortorgid"]))]
    app, db, sec = create_app("advisory", title="Advisory", migrations_dir=MIGRATIONS, settings=settings, db=db, security=security, consumers=consumers)
    intel = intelligence or UpstreamClient("advisory", "intelligence", sec.service_auth)
    bill = billing or UpstreamClient("advisory", "billing", sec.service_auth)
    models = chain or build_chain()
    ctx_dep = sec.context_dependency()
    r = APIRouter()

    def viewer(ctx: AccessContext = Depends(ctx_dep)) -> AccessContext:
        require_sme_access(ctx, "VIEW_PROFILE")
        return ctx

    @r.get("/v1/assessments/{assessment_id}/explanation")
    def explanation(assessment_id: uuid.UUID, ctx: AccessContext = Depends(viewer)):
        return svc.explain(db, intel, bill, models, ctx, assessment_id, None)

    @r.post("/v1/scenarios/{scenario_id}/explanation")
    def scenario_explanation(scenario_id: uuid.UUID, body: ScenarioExplain, ctx: AccessContext = Depends(viewer)):
        return svc.explain(db, intel, bill, models, ctx, body.assessment_id, scenario_id)

    @r.post("/v1/assistant/chat")
    def assistant_chat(body: ChatIn, ctx: AccessContext = Depends(viewer)):
        if body.messages[-1].role != "user":
            raise Unprocessable("the last message must be the question", code="invalid_chat")
        return svc.chat(db, intel, bill, models, ctx, body.assessment_id, [m.model_dump() for m in body.messages])

    app.include_router(r)
    return app


def app_factory():
    return create_service_app()
