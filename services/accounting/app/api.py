from __future__ import annotations

import time
import urllib.parse
import uuid
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel

from credsort_common.config import env
from credsort_common.db import Database
from credsort_common.errors import Forbidden, Unprocessable, UpstreamUnavailable
from credsort_common.security import AccessContext, Security, require_sme_access

from . import service as svc
from .plugins import bexio
from .plugins.base import ProviderError
from .plugins.registry import encrypt_token


class ConnectionCreate(BaseModel):
    source_type: Literal["SYNTHETIC", "BEXIO"]
    dataset: Literal["muster", "alpina", "pixelwerk"] = "muster"


class ImportStart(BaseModel):
    connection_id: uuid.UUID


class BexioCallback(BaseModel):
    code: str
    state: str


def build_router(db: Database, sec: Security) -> APIRouter:
    r = APIRouter()
    ctx_dep = sec.context_dependency()
    internal = sec.service_dependency({"intelligence"})

    def sme(ctx: AccessContext = Depends(ctx_dep)) -> AccessContext:
        require_sme_access(ctx, "PREPARE_APPLICATION")
        return ctx

    @r.post("/v1/connections", status_code=201)
    def create_connection(body: ConnectionCreate, ctx: AccessContext = Depends(sme)):
        return svc.create_connection(db, ctx, body.source_type, body.dataset)

    @r.get("/v1/connections")
    def connections(ctx: AccessContext = Depends(ctx_dep)):
        require_sme_access(ctx, "VIEW_PROFILE")
        return svc.list_connections(db, ctx)

    @r.delete("/v1/connections/{connection_id}", status_code=204)
    def revoke(connection_id: uuid.UUID, ctx: AccessContext = Depends(sme)):
        svc.revoke_connection(db, ctx, connection_id)

    @r.post("/v1/import-jobs", status_code=202)
    def start(body: ImportStart, response: Response, ctx: AccessContext = Depends(sme),
              idempotency_key: Annotated[str | None, Header()] = None):
        status, job = svc.start_import(db, ctx, body.connection_id, idempotency_key)
        response.status_code = status
        response.headers["Location"] = job["location"]
        return job

    @r.get("/v1/import-jobs/{job_id}")
    def job(job_id: uuid.UUID, ctx: AccessContext = Depends(ctx_dep)):
        require_sme_access(ctx, "VIEW_PROFILE")
        return svc.get_job(db, ctx, job_id)

    @r.get("/v1/import-jobs")
    def jobs(connection_id: uuid.UUID | None = None, ctx: AccessContext = Depends(ctx_dep)):
        require_sme_access(ctx, "VIEW_PROFILE")
        return svc.list_jobs(db, ctx, connection_id)

    # ---- bexio OAuth (UNVERIFIED against the sandbox, see plugins/bexio.py) ----
    @r.get("/v1/connections/bexio/authorize")
    def bexio_authorize(ctx: AccessContext = Depends(sme)):
        client_id = env("BEXIO_CLIENT_ID")
        if not client_id:
            raise Unprocessable("bexio is not configured: set BEXIO_CLIENT_ID and BEXIO_CLIENT_SECRET", code="bexio_not_configured")
        state = jwt.encode({"org": str(ctx.effective_org_id), "exp": int(time.time()) + 600}, env("SERVICE_TOKEN_SECRET", "dev-only-service-secret-change-me-0123456789"), algorithm="HS256")
        query = urllib.parse.urlencode({"client_id": client_id, "redirect_uri": env("BEXIO_REDIRECT_URI", "http://localhost:3000/api/bexio/callback"),
                                        "response_type": "code", "scope": env("BEXIO_SCOPES", "openid offline_access accounting_read"), "state": state})
        return {"url": f"{env('BEXIO_AUTH_URL', 'https://auth.bexio.com/realms/bexio/protocol/openid-connect/auth')}?{query}", "state": state}

    @r.post("/v1/connections/bexio/callback", status_code=201)
    def bexio_callback(body: BexioCallback, ctx: AccessContext = Depends(sme)):
        try:
            claims = jwt.decode(body.state, env("SERVICE_TOKEN_SECRET", "dev-only-service-secret-change-me-0123456789"), algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise Forbidden("invalid OAuth state", code="invalid_state") from exc
        if claims["org"] != str(ctx.effective_org_id):
            raise Forbidden("OAuth state belongs to another organization", code="invalid_state")
        try:
            access_token = bexio.exchange_code(body.code)
        except ProviderError as exc:
            raise UpstreamUnavailable("bexio token exchange failed", code="bexio_unavailable") from exc
        created = svc.create_connection(db, ctx, "BEXIO", "muster")
        with db.session(ctx.effective_org_id) as s:
            from sqlalchemy import text
            s.execute(text("update data_connections set token_enc = :t where id = :i"), {"t": encrypt_token(access_token), "i": created["id"]})
        return created

    # ---- internal claim check (ADR-0023): Intelligence fetches the ledger of a batch it was told about ----
    @r.get("/internal/v1/batches/{batch_id}/ledger")
    def ledger(batch_id: uuid.UUID, org_id: uuid.UUID = Query(...), caller: str = Depends(internal)):
        return svc.ledger_for_batch(db, org_id, batch_id)

    return r
