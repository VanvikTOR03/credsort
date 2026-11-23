"""Advisory: explanations of verified results. It has no access to financial databases (ADR-0009, FF-C8)."""
from __future__ import annotations

import hashlib
import json
import logging
import uuid

from sqlalchemy import text

from credsort_common.audit import record_audit
from credsort_common.db import Database
from credsort_common.errors import Forbidden, UpstreamHTTPError, UpstreamUnavailable
from credsort_common.events import jsonable
from credsort_common.lifecycle import finish_deletion
from credsort_common.security import AccessContext

from .domain import text as T
from .plugins.models import LanguageModel

SVC = "advisory"
log = logging.getLogger("credsort.advisory")


def entitlements_for(db: Database, billing, ctx: AccessContext) -> list[str]:
    org = ctx.effective_org_id
    with db.session(org) as s:
        row = s.execute(text("select entitlements from entitlements where org_id = :o"), {"o": org}).first()
    if row:
        return list(row.entitlements)
    try:
        got = billing.get(f"/internal/v1/organizations/{org}/entitlements", ctx=ctx)
    except (UpstreamUnavailable, UpstreamHTTPError) as exc:  # fail closed
        raise UpstreamUnavailable("plan information is temporarily unavailable; please try again", code="entitlements_unavailable") from exc
    with db.session(org) as s:
        s.execute(text("insert into entitlements(org_id, entitlements) values (:o, :e) on conflict (org_id) do update set entitlements = excluded.entitlements, updated_at = now()"),
                  {"o": org, "e": got["entitlements"]})
    return list(got["entitlements"])


def explain(db: Database, intel, billing, chain: list[LanguageModel], ctx: AccessContext, assessment_id: uuid.UUID, scenario_id: uuid.UUID | None) -> dict:
    needed = "WHAT_IF" if scenario_id else "ADVISOR"
    if needed not in entitlements_for(db, billing, ctx):
        raise Forbidden("this feature is not part of your plan", code="feature_not_included")
    kind = "scenario" if scenario_id else "assessment"
    context = intel.get(f"/internal/v1/assessments/{assessment_id}/advisory-context", ctx=ctx, params={"scenario_id": str(scenario_id)} if scenario_id else None)
    digest = hashlib.sha256(json.dumps(context, sort_keys=True, default=str).encode()).hexdigest()[:24]
    org = ctx.effective_org_id
    for model in chain:
        key = f"{kind}:{digest}:{model.name}:{model.version}"
        with db.session(org) as s:
            cached = s.execute(text("select body from explanation_cache where org_id = :o and key = :k"), {"o": org, "k": key}).first()
        if cached:
            return {**cached.body, "cached": True}
        try:
            out = model.explain(kind, context)
            bad = T.invented_numbers(out, context)
            if bad:  # the model produced a number that is not in the verified context: discard it (FF-F4)
                log.warning("model output rejected: invented numbers", extra={"code": "invented_numbers"})
                continue
        except Exception:
            log.warning("model failed, trying the next one", extra={"code": "model_failed"})
            continue
        body = jsonable({**out, "assessment_id": assessment_id, "scenario_id": scenario_id, "model": {"name": model.name, "version": model.version},
                         "fallback_used": model is not chain[0], "disclaimer": T.DISCLAIMER})
        with db.session(org) as s:
            s.execute(text("insert into explanation_cache(org_id, key, body) values (:o, :k, cast(:b as jsonb)) on conflict do nothing"), {"o": org, "k": key, "b": json.dumps(body)})
            record_audit(s, SVC, ctx, "explanation.created", f"assessment/{assessment_id}")
        return {**body, "cached": False}
    raise UpstreamUnavailable("no explanation could be produced", code="explanation_unavailable")


def chat(db: Database, intel, billing, chain: list[LanguageModel], ctx: AccessContext, assessment_id: uuid.UUID, messages: list[dict]) -> dict:
    """The company's coach: answers questions about the company's own verified assessment. Same guard as explanations: no invented numbers."""
    if "ADVISOR" not in entitlements_for(db, billing, ctx):
        raise Forbidden("this feature is not part of your plan", code="feature_not_included")
    context = intel.get(f"/internal/v1/assessments/{assessment_id}/advisory-context", ctx=ctx)
    owner_numbers = [{"value": str(n)} for m in messages if m["role"] == "user" for n in T.numbers_in(m["content"])]  # numbers the owner typed may be repeated
    guard_context = {**context, "owner_numbers": owner_numbers}
    org = ctx.effective_org_id
    for model in chain:
        try:
            reply = model.chat(messages, context)
            if not reply or T.invented_numbers({"reply": reply}, guard_context, rounding=True):
                log.warning("assistant reply rejected", extra={"code": "invented_numbers"})
                continue
        except Exception:
            log.warning("assistant model failed, trying the next one", extra={"code": "model_failed"})
            continue
        with db.session(org) as s:
            record_audit(s, SVC, ctx, "assistant.replied", f"assessment/{assessment_id}")
        return {"reply": reply, "model": {"name": model.name, "version": model.version}, "fallback_used": model is not chain[0], "disclaimer": T.DISCLAIMER}
    raise UpstreamUnavailable("the assistant is not available right now", code="assistant_unavailable")


def upsert_entitlements(session, event) -> None:
    d = event["data"]
    session.execute(text("insert into entitlements(org_id, entitlements) values (:o, :e) on conflict (org_id) do update set entitlements = excluded.entitlements, updated_at = now()"),
                    {"o": d["org_id"], "e": d["entitlements"]})


def delete_org_data(session, org_id) -> None:
    session.execute(text("delete from explanation_cache where org_id = :o"), {"o": org_id})
    session.execute(text("delete from entitlements where org_id = :o"), {"o": org_id})
    finish_deletion(session, SVC, org_id)
