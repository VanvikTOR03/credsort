"""Financial Intelligence use cases: the pipeline's second half and the profile APIs (ADR-0002, ADR-0025, ADR-0026)."""
from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import text

from credsort_common.audit import record_audit
from credsort_common.db import Database
from credsort_common.errors import Forbidden, NotFound, Unprocessable, UpstreamHTTPError, UpstreamUnavailable
from credsort_common.events import emit, jsonable
from credsort_common.lifecycle import finish_deletion
from credsort_common.money import D, q_ratio
from credsort_common.security import AccessContext

from .domain import mapping as mapping_dom
from .domain import scenario as scenario_dom
from .domain import scorecard as sc
from .domain.metrics import CATALOGUE, FORMULA_VERSION, compute_metrics
from .domain.snapshot import PipelineError, build_snapshot

SVC = "intelligence"

# Fields a lender may be allowed to use (SME-consented, ADR-0008). Values are frozen by Marketplace at publication (ADR-0026).
FIELD_CATALOGUE = ["assessment_category", "assessment_score", "confidence_band", "revenue_band", "revenue", "revenue_growth", "ebitda_margin",
                   "net_profit_margin", "current_ratio", "working_capital", "equity_ratio", "debt_to_ebitda", "dscr"]


def ensure_reference_data(db: Database) -> None:
    with db.system() as s:
        s.execute(text("insert into mapping_versions(id, rules) values (:i, cast(:r as jsonb)) on conflict do nothing"),
                  {"i": mapping_dom.MAPPING_VERSION, "r": json.dumps(mapping_dom.definition())})
        s.execute(text("insert into scorecard_versions(id, definition) values (:i, cast(:r as jsonb)) on conflict do nothing"),
                  {"i": sc.SCORECARD_VERSION, "r": json.dumps(sc.definition())})


# --------------------------------------------------------------------------- pipeline
def _failure(session, org_id, batch_id, code: str) -> None:
    session.execute(text("insert into pipeline_failures(id, org_id, batch_id, reason_code) values (:i, :o, :b, :c)"),
                    {"i": uuid.uuid4(), "o": org_id, "b": batch_id, "c": code})
    emit(session, SVC, "intelligence.assessment.failed", org_id, f"batch/{batch_id}", {"org_id": org_id, "batch_id": batch_id, "reason_code": code})
    record_audit(session, SVC, None, "assessment.failed", f"batch/{batch_id}", org_id=org_id)


def run_pipeline(session, org_id, ledger: dict, as_of: date) -> uuid.UUID | None:
    """Stages 4-6 in ONE transaction: a snapshot never exists without its metrics and assessment (ADR-0025)."""
    batch_id = uuid.UUID(str(ledger["batch_id"]))
    if session.execute(text("select 1 from snapshots where batch_id = :b and mapping_version = :m"), {"b": batch_id, "m": mapping_dom.MAPPING_VERSION}).first():
        return None  # redelivered or re-imported identical batch: no duplicates
    try:
        snapshot = build_snapshot(ledger)
        metrics = compute_metrics(snapshot)
        result = sc.assess(metrics)
        if result["score"] is None:
            raise PipelineError("INSUFFICIENT_DATA", "no indicator could be rated")
    except PipelineError as exc:
        _failure(session, org_id, batch_id, exc.code)
        return None
    conf = sc.confidence(metrics, snapshot, as_of)
    snapshot_id, assessment_id = uuid.uuid4(), uuid.uuid4()
    session.execute(text("insert into snapshots(id, org_id, batch_id, mapping_version, source_type, period_start, period_end, data) "
                         "values (:i, :o, :b, :m, :t, :ps, :pe, cast(:d as jsonb))"),
                    {"i": snapshot_id, "o": org_id, "b": batch_id, "m": mapping_dom.MAPPING_VERSION, "t": ledger["source_type"],
                     "ps": snapshot["period"]["start"], "pe": snapshot["period"]["end"], "d": json.dumps(snapshot)})
    session.execute(text("insert into metrics(id, org_id, snapshot_id, code, value, unit, status, reason, formula_version) "
                         "values (:i, :o, :s, :c, :v, :u, :st, :r, :f)"),
                    [{"i": uuid.uuid4(), "o": org_id, "s": snapshot_id, "c": m["code"], "v": m["value"], "u": m["unit"], "st": m["status"],
                      "r": m["reason"], "f": m["formula_version"]} for m in metrics])
    session.execute(text("insert into assessments(id, org_id, snapshot_id, scorecard_version, confidence_model_version, as_of, score, category, factors, confidence) "
                         "values (:i, :o, :s, :sv, :cv, :a, :sc, :cat, cast(:f as jsonb), cast(:c as jsonb))"),
                    {"i": assessment_id, "o": org_id, "s": snapshot_id, "sv": sc.SCORECARD_VERSION, "cv": sc.CONFIDENCE_VERSION, "a": as_of,
                     "sc": result["score"], "cat": result["category"], "f": json.dumps(result["factors"]), "c": json.dumps(conf)})
    emit(session, SVC, "intelligence.snapshot.created", org_id, f"snapshot/{snapshot_id}", {"org_id": org_id, "snapshot_id": snapshot_id, "batch_id": batch_id})
    emit(session, SVC, "intelligence.assessment.created", org_id, f"assessment/{assessment_id}",
         {"org_id": org_id, "assessment_id": assessment_id, "snapshot_id": snapshot_id, "scorecard_version": sc.SCORECARD_VERSION,
          "mapping_version": mapping_dom.MAPPING_VERSION})
    record_audit(session, SVC, None, "assessment.created", f"assessment/{assessment_id}", org_id=org_id)
    return assessment_id


# --------------------------------------------------------------------------- reads
def _metric(r) -> dict:
    return {"code": r.code, "label": CATALOGUE[r.code][0], "value": r.value, "unit": r.unit, "status": r.status, "reason": r.reason, "formula_version": r.formula_version}


def _load(session, where: str, params: dict) -> dict | None:
    a = session.execute(text("select a.id, a.snapshot_id, a.scorecard_version, a.confidence_model_version, a.as_of, a.score, a.category, a.factors, a.confidence, "
                             "a.created_at, s.period_start, s.period_end, s.source_type, s.mapping_version, s.batch_id from assessments a "
                             f"join snapshots s on s.id = a.snapshot_id where {where} order by a.created_at desc limit 1"), params).first()
    if not a:
        return None
    metrics = session.execute(text("select code, value, unit, status, reason, formula_version from metrics where snapshot_id = :s order by code"), {"s": a.snapshot_id}).all()
    label = {"A": "Strong", "B": "Solid", "C": "Watch", "D": "Weak"}[a.category]
    return {"assessment": {"id": a.id, "category": a.category, "label": label, "score": a.score, "factors": a.factors, "confidence": a.confidence, "as_of": a.as_of,
                           "created_at": a.created_at, "disclaimer": "Preliminary, illustrative assessment. Not a bank rating and not a probability of default."},
            "snapshot": {"id": a.snapshot_id, "period_start": a.period_start, "period_end": a.period_end, "source_type": a.source_type, "batch_id": a.batch_id},
            "versions": {"scorecard": a.scorecard_version, "confidence": a.confidence_model_version, "mapping": a.mapping_version, "formula": FORMULA_VERSION},
            "metrics": [_metric(m) for m in metrics]}


def current_profile(db: Database, ctx: AccessContext) -> dict:
    with db.session(ctx.effective_org_id) as s:
        p = _load(s, "true", {})
        failure = s.execute(text("select reason_code, created_at from pipeline_failures order by created_at desc limit 1")).first()
    if p is None:
        raise NotFound("no financial profile yet", code="no_profile", extra={"last_failure": failure.reason_code if failure else None})
    return p


def get_assessment(db: Database, ctx: AccessContext, assessment_id: uuid.UUID) -> dict:
    with db.session(ctx.effective_org_id) as s:
        p = _load(s, "a.id = :i", {"i": assessment_id})
    if p is None:
        raise NotFound("assessment not found")
    return p


def list_assessments(db: Database, ctx: AccessContext) -> list[dict]:
    with db.session(ctx.effective_org_id) as s:
        rows = s.execute(text("select a.id, a.category, a.score, a.created_at, s.period_end, s.source_type from assessments a join snapshots s on s.id = a.snapshot_id "
                              "order by a.created_at desc limit 20")).all()
    return [dict(r._mapping) for r in rows]


# --------------------------------------------------------------------------- internal extracts
def _band(revenue: Decimal) -> str:
    return "<1M" if revenue < 1_000_000 else "1-5M" if revenue < 5_000_000 else "5-20M" if revenue < 20_000_000 else ">20M"


def profile_extract(db: Database, ctx: AccessContext, assessment_id: uuid.UUID, fields: list[str]) -> dict:
    """The ONLY financial data that leaves this service towards the marketplace: the fields the SME chose (ADR-0008, ADR-0026)."""
    unknown = sorted(set(fields) - set(FIELD_CATALOGUE))
    if unknown or not fields:
        raise Unprocessable(f"unknown or empty field list: {unknown}", code="unknown_fields")
    with db.session(ctx.effective_org_id) as s:
        p = _load(s, "a.id = :i", {"i": assessment_id})
        if p is None:
            raise NotFound("assessment not found")
        metrics = {m["code"]: m for m in p["metrics"]}
        values: dict = {}
        for f in fields:
            if f == "assessment_category":
                values[f] = p["assessment"]["category"]
            elif f == "assessment_score":
                values[f] = p["assessment"]["score"]
            elif f == "confidence_band":
                values[f] = p["assessment"]["confidence"]["band"]
            elif f == "revenue_band":
                values[f] = _band(D(metrics["revenue"]["value"]))
            else:
                m = metrics[f]
                values[f] = None if m["status"] != "OK" else format(D(m["value"]), "f")
        record_audit(s, SVC, ctx, "profile.extracted", f"assessment/{assessment_id}")
    return {"assessment_id": assessment_id, "as_of": p["assessment"]["as_of"], "period_end": p["snapshot"]["period_end"], "fields": values,
            "versions": p["versions"]}


def advisory_context(db: Database, ctx: AccessContext, assessment_id: uuid.UUID, scenario_id: uuid.UUID | None) -> dict:
    """Aggregates only (no ledger entries, no counterparties) for the AI explanation layer (ADR-0009)."""
    with db.session(ctx.effective_org_id) as s:
        p = _load(s, "a.id = :i", {"i": assessment_id})
        if p is None:
            raise NotFound("assessment not found")
        scenario = None
        if scenario_id:
            row = s.execute(text("select id, inputs, result from scenarios where id = :i and assessment_id = :a"), {"i": scenario_id, "a": assessment_id}).first()
            if not row:
                raise NotFound("scenario not found")
            scenario = {"id": row.id, "inputs": row.inputs, "result": row.result}
        record_audit(s, SVC, ctx, "advisory.context.read", f"assessment/{assessment_id}")
    return {"assessment": p["assessment"], "period_end": p["snapshot"]["period_end"], "metrics": p["metrics"], "versions": p["versions"], "scenario": scenario}


# --------------------------------------------------------------------------- entitlements + scenarios
def entitlements_for(db: Database, billing, ctx: AccessContext) -> list[str]:
    org = ctx.effective_org_id
    with db.session(org) as s:
        row = s.execute(text("select entitlements from entitlements where org_id = :o"), {"o": org}).first()
    if row:
        return list(row.entitlements)
    try:  # cache miss: ask Billing (C7). Failing closed when Billing is unreachable.
        got = billing.get(f"/internal/v1/organizations/{org}/entitlements", ctx=ctx)
    except (UpstreamUnavailable, UpstreamHTTPError) as exc:
        raise UpstreamUnavailable("plan information is temporarily unavailable; please try again", code="entitlements_unavailable") from exc
    with db.session(org) as s:
        s.execute(text("insert into entitlements(org_id, entitlements) values (:o, :e) on conflict (org_id) do update set entitlements = excluded.entitlements, updated_at = now()"),
                  {"o": org, "e": got["entitlements"]})
    return list(got["entitlements"])


def run_scenario(db: Database, billing, ctx: AccessContext, assessment_id: uuid.UUID, inputs: dict) -> dict:
    if "WHAT_IF" not in entitlements_for(db, billing, ctx):
        raise Forbidden("what-if analysis is not part of your plan", code="feature_not_included")
    with db.session(ctx.effective_org_id) as s:
        row = s.execute(text("select s.data from assessments a join snapshots s on s.id = a.snapshot_id where a.id = :i"), {"i": assessment_id}).first()
        if not row:
            raise NotFound("assessment not found")
        result = jsonable(scenario_dom.run(row.data, inputs))  # on a copy; the baseline snapshot is never changed
        sid = uuid.uuid4()
        s.execute(text("insert into scenarios(id, org_id, assessment_id, inputs, result) values (:i, :o, :a, cast(:inp as jsonb), cast(:r as jsonb))"),
                  {"i": sid, "o": ctx.effective_org_id, "a": assessment_id, "inp": json.dumps(inputs), "r": json.dumps(result)})
        record_audit(s, SVC, ctx, "scenario.created", f"scenario/{sid}")
    return {"id": sid, "assessment_id": assessment_id, "inputs": inputs, **result}


def upsert_entitlements(session, event) -> None:
    d = event["data"]
    session.execute(text("insert into entitlements(org_id, entitlements) values (:o, :e) on conflict (org_id) do update set entitlements = excluded.entitlements, updated_at = now()"),
                    {"o": d["org_id"], "e": d["entitlements"]})


def delete_org_data(session, org_id) -> None:
    for table in ("scenarios", "assessments", "metrics", "snapshots", "pipeline_failures", "entitlements"):
        session.execute(text(f"delete from {table} where org_id = :o"), {"o": org_id})
    finish_deletion(session, SVC, org_id)
