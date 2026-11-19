"""SME side of the marketplace: applications, publication with consent, disclosure, access requests, dispute (ADR-0008, ADR-0026)."""
from __future__ import annotations

import datetime as dt
import json
import uuid
from decimal import Decimal

from sqlalchemy import text

from credsort_common.audit import record_audit
from credsort_common.db import Database
from credsort_common.errors import Conflict, Forbidden, NotFound, Unprocessable
from credsort_common.events import emit
from credsort_common.idempotency import lookup_idempotent, run_idempotent
from credsort_common.security import AccessContext, forbid_delegated, require_role, require_sme_access, require_verified

from .domain import fields as F
from .domain.lifecycle import DISPUTE_WINDOW, APPLICATION, can_move
from .sessions import as_system, pilot_cap, sess

SVC = "marketplace"
APP_COLS = ("id, sme_org_id, status, amount, term_months, purpose, collateral, assessment_id, industry, employees, published_profile_id, selected_offer_id, "
            "created_at, published_at, selected_at, funded_at, dispute_until, disputed_at, closed_at")


def _app(row) -> dict:
    return dict(row._mapping)


def _load_app(s, app_id: uuid.UUID, lock: bool = False):
    row = s.execute(text(f"select {APP_COLS} from applications where id = :i{' for update' if lock else ''}"), {"i": app_id}).first()
    if not row:
        raise NotFound("application not found")
    return row


def _check_amount(amount: Decimal) -> None:
    cap = pilot_cap()
    if cap is not None and amount > cap:
        raise Unprocessable(f"during the pilot the requested amount is limited to CHF {cap:,.0f}", code="pilot_cap_exceeded")


# --------------------------------------------------------------------------- drafts
def create_application(db: Database, ctx: AccessContext, amount: Decimal, term_months: int, purpose: str | None, collateral: str | None,
                       assessment_id: uuid.UUID | None) -> dict:
    require_sme_access(ctx, "PREPARE_APPLICATION")
    _check_amount(amount)
    app_id = uuid.uuid4()
    with sess(db, ctx) as s:
        s.execute(text("insert into applications(id, sme_org_id, amount, term_months, purpose, collateral, assessment_id) values (:i, :o, :a, :t, :p, :c, :as)"),
                  {"i": app_id, "o": ctx.effective_org_id, "a": amount, "t": term_months, "p": purpose, "c": collateral, "as": assessment_id})
        record_audit(s, SVC, ctx, "application.created", f"application/{app_id}")
        return _app(_load_app(s, app_id))


def update_application(db: Database, ctx: AccessContext, app_id: uuid.UUID, changes: dict) -> dict:
    require_sme_access(ctx, "PREPARE_APPLICATION")
    if "amount" in changes:
        _check_amount(changes["amount"])
    with sess(db, ctx) as s:
        row = _load_app(s, app_id, lock=True)
        if row.status != "DRAFT":
            raise Conflict("only drafts can be edited; a published application is frozen", code="not_a_draft")
        allowed = {k: v for k, v in changes.items() if k in ("amount", "term_months", "purpose", "collateral", "assessment_id") and v is not None}
        for k, v in allowed.items():
            s.execute(text(f"update applications set {k} = :v where id = :i"), {"v": v, "i": app_id})
        record_audit(s, SVC, ctx, "application.updated", f"application/{app_id}")
        return _app(_load_app(s, app_id))


def get_application(db: Database, ctx: AccessContext, app_id: uuid.UUID) -> dict:
    require_sme_access(ctx, "VIEW_PROFILE")
    with sess(db, ctx) as s:
        app = _app(_load_app(s, app_id))
        app["disclosures"] = [dict(r._mapping) for r in s.execute(
            text("select id, lender_org_id, level, purpose, permitted_fields, granted_at, revoked_at from disclosures where application_id = :a order by granted_at"), {"a": app_id})]
        profile = s.execute(text("select fields, as_of, version from published_profiles where id = :p"), {"p": app["published_profile_id"]}).first() if app["published_profile_id"] else None
        app["published_profile"] = dict(profile._mapping) if profile else None
        app["offer_count"] = s.execute(text("select count(*) from offers where application_id = :a and status = 'SUBMITTED'"), {"a": app_id}).scalar()
    return app


def list_applications(db: Database, ctx: AccessContext) -> list[dict]:
    require_sme_access(ctx, "VIEW_PROFILE")
    with sess(db, ctx) as s:
        rows = s.execute(text(f"select {APP_COLS}, (select count(*) from offers o where o.application_id = applications.id and o.status = 'SUBMITTED') as open_offers "
                              "from applications order by created_at desc limit 50")).all()
    return [_app(r) for r in rows]


# --------------------------------------------------------------------------- publication
def _marketplace_values(app, ctx: AccessContext, fields: list[str]) -> dict:
    industry = app.industry or (None if ctx.delegated else ctx.industry)
    employees = app.employees if app.employees is not None else (None if ctx.delegated else ctx.employees)
    values = {"requested_amount": format(app.amount, "f"), "term_months": app.term_months, "industry": industry,
              "employees_band": F.employees_band(employees), "purpose": app.purpose, "collateral": app.collateral,
              "company_name": None if ctx.delegated else ctx.org_name}
    return {f: values[f] for f in fields}


def _fetch_intelligence(intel, ctx: AccessContext, assessment_id: uuid.UUID, fields: list[str]) -> dict:
    if not fields:
        return {"fields": {}, "as_of": dt.date.today().isoformat()}
    return intel.get(f"/internal/v1/assessments/{assessment_id}/profile-extract", ctx=ctx, params={"fields": ",".join(fields)})


def _validated_fields(fields: list[str]) -> tuple[list[str], list[str]]:
    if not fields:
        raise Unprocessable("choose at least one field to share", code="no_fields")
    try:
        return F.split(list(dict.fromkeys(fields)))
    except ValueError as exc:
        raise Unprocessable(str(exc), code="unknown_fields") from exc


def publication_preview(db: Database, intel, ctx: AccessContext, app_id: uuid.UUID, fields: list[str]) -> dict:
    """"What lenders see": exactly the values that would be frozen if the SME publishes now (ADR-0026)."""
    require_sme_access(ctx, "PREPARE_APPLICATION")
    intel_fields, own_fields = _validated_fields(fields)
    with sess(db, ctx) as s:
        app = _load_app(s, app_id)
    if app.status != "DRAFT":
        raise Conflict("this application is already published", code="not_a_draft")
    if app.assessment_id is None:
        raise Unprocessable("create a financial profile first", code="no_assessment")
    extract = _fetch_intelligence(intel, ctx, app.assessment_id, intel_fields)  # remote call, outside any transaction
    values = {**extract["fields"], **_marketplace_values(app, ctx, own_fields)}
    return {"application_id": app_id, "assessment_id": app.assessment_id, "as_of": extract.get("as_of"),
            "fields": [{"field": f, "label": F.CATALOGUE[f], "value": values.get(f)} for f in fields if f in values]}


def publish(db: Database, intel, ctx: AccessContext, app_id: uuid.UUID, fields: list[str], lender_org_ids: list[uuid.UUID] | None,
            assessment_id: uuid.UUID | None, idem_key: str | None) -> tuple[int, dict]:
    forbid_delegated(ctx)
    require_role(ctx, "SME_ADMIN")  # delegation never includes granting disclosure (ADR-0019)
    require_verified(ctx)
    intel_fields, own_fields = _validated_fields(fields)
    fingerprint = {"app": str(app_id), "fields": sorted(fields), "lenders": sorted(str(x) for x in lender_org_ids or [])}
    with sess(db, ctx) as s:
        replay = lookup_idempotent(s, ctx.effective_org_id, idem_key, fingerprint)
        if replay:
            return replay
        app = _load_app(s, app_id)
    if app.status != "DRAFT":
        raise Conflict("this application is already published", code="not_a_draft")
    use_assessment = assessment_id or app.assessment_id
    if use_assessment is None:
        raise Unprocessable("create a financial profile first", code="no_assessment")
    extract = _fetch_intelligence(intel, ctx, use_assessment, intel_fields)  # outside the transaction
    org = ctx.effective_org_id
    with sess(db, ctx) as s:
        def action() -> tuple[int, dict]:
            row = _load_app(s, app_id, lock=True)
            if not can_move(APPLICATION, row.status, "PUBLISHED"):
                raise Conflict("this application is already published", code="not_a_draft")
            s.execute(text("update applications set industry = :ind, employees = :emp where id = :i"), {"ind": ctx.industry, "emp": ctx.employees, "i": app_id})
            row = _load_app(s, app_id)
            values = {**extract["fields"], **_marketplace_values(row, ctx, own_fields)}
            profile_id = uuid.uuid4()
            as_of = dt.date.fromisoformat(str(extract["as_of"]))
            s.execute(text("insert into published_profiles(id, application_id, sme_org_id, assessment_id, fields, as_of) values (:i, :a, :o, :as, cast(:f as jsonb), :d)"),
                      {"i": profile_id, "a": app_id, "o": org, "as": use_assessment, "f": json.dumps(values), "d": as_of})
            s.execute(text("update applications set status = 'PUBLISHED', published_at = now(), published_profile_id = :p, assessment_id = :as where id = :i"),
                      {"p": profile_id, "as": use_assessment, "i": app_id})
            for lender in (lender_org_ids or [None]):
                s.execute(text("insert into disclosures(id, application_id, sme_org_id, lender_org_id, level, purpose, permitted_fields, profile_id) "
                               "values (:i, :a, :o, :l, 'summary', 'matching', :f, :p)"),
                          {"i": uuid.uuid4(), "a": app_id, "o": org, "l": lender, "f": list(values), "p": profile_id})
                emit(s, SVC, "marketplace.disclosure.granted", org, f"application/{app_id}", {"application_id": app_id, "sme_org_id": org, "lender_org_id": lender, "level": "summary"})
            emit(s, SVC, "marketplace.application.published", org, f"application/{app_id}", {"application_id": app_id, "sme_org_id": org})
            record_audit(s, SVC, ctx, "application.published", f"application/{app_id}")
            return 201, {"application_id": app_id, "status": "PUBLISHED", "profile_id": profile_id, "shared_fields": list(values)}
        return run_idempotent(s, org, idem_key, fingerprint, action)


def withdraw(db: Database, ctx: AccessContext, app_id: uuid.UUID) -> dict:
    forbid_delegated(ctx)
    require_role(ctx, "SME_ADMIN")
    org = ctx.effective_org_id
    with sess(db, ctx) as s:
        row = _load_app(s, app_id, lock=True)
        if not can_move(APPLICATION, row.status, "WITHDRAWN"):
            raise Conflict(f"a {row.status.lower()} application cannot be withdrawn", code="invalid_state")
        s.execute(text("update applications set status = 'WITHDRAWN', closed_at = now() where id = :i"), {"i": app_id})
        s.execute(text("update offers set status = 'REJECTED' where application_id = :i and status = 'SUBMITTED'"), {"i": app_id})
        for d in s.execute(text("update disclosures set revoked_at = now() where application_id = :i and revoked_at is null returning lender_org_id, level"), {"i": app_id}).all():
            emit(s, SVC, "marketplace.disclosure.revoked", org, f"application/{app_id}", {"application_id": app_id, "sme_org_id": org, "lender_org_id": d.lender_org_id, "level": d.level})
        emit(s, SVC, "marketplace.application.withdrawn", org, f"application/{app_id}", {"application_id": app_id, "sme_org_id": org})
        record_audit(s, SVC, ctx, "application.withdrawn", f"application/{app_id}")
    return {"application_id": app_id, "status": "WITHDRAWN"}


# --------------------------------------------------------------------------- disclosure (revocation is immediate: same database as matching)
def list_disclosures(db: Database, ctx: AccessContext) -> list[dict]:
    require_sme_access(ctx, "VIEW_PROFILE")
    with sess(db, ctx) as s:
        rows = s.execute(text("select id, application_id, lender_org_id, level, purpose, permitted_fields, granted_at from disclosures where revoked_at is null order by granted_at desc")).all()
    return [dict(r._mapping) for r in rows]


def _revoke(s, ctx, org, where: str, params: dict) -> int:
    rows = s.execute(text(f"update disclosures set revoked_at = now() where revoked_at is null and sme_org_id = :o and {where} returning id, application_id, lender_org_id, level"),
                     {"o": org, **params}).all()
    for d in rows:
        emit(s, SVC, "marketplace.disclosure.revoked", org, f"application/{d.application_id}",
             {"application_id": d.application_id, "sme_org_id": org, "lender_org_id": d.lender_org_id, "level": d.level})
        record_audit(s, SVC, ctx, "disclosure.revoked", f"disclosure/{d.id}")
    return len(rows)


def revoke_disclosure(db: Database, ctx: AccessContext, disclosure_id: uuid.UUID) -> dict:
    forbid_delegated(ctx)
    require_role(ctx, "SME_ADMIN")
    with sess(db, ctx) as s:
        if not _revoke(s, ctx, ctx.effective_org_id, "id = :d", {"d": disclosure_id}):
            raise NotFound("active disclosure not found")
    return {"revoked": 1, "note": "Lenders can no longer see this data. Copies a lender already received cannot be recalled."}


def revoke_all(db: Database, ctx: AccessContext) -> dict:
    forbid_delegated(ctx)
    require_role(ctx, "SME_ADMIN")
    with sess(db, ctx) as s:
        n = _revoke(s, ctx, ctx.effective_org_id, "true", {})
    return {"revoked": n, "note": "Lenders can no longer see this data. Copies a lender already received cannot be recalled."}


# --------------------------------------------------------------------------- access requests (full disclosure)
def list_access_requests(db: Database, ctx: AccessContext, app_id: uuid.UUID | None) -> list[dict]:
    require_sme_access(ctx, "VIEW_PROFILE")
    with sess(db, ctx) as s:
        rows = s.execute(text("select id, application_id, lender_org_id, requested_fields, status, created_at, decided_at from access_requests "
                              "where (cast(:a as uuid) is null or application_id = cast(:a as uuid)) order by created_at desc"), {"a": app_id}).all()
    return [dict(r._mapping) for r in rows]


def decide_access_request(db: Database, intel, ctx: AccessContext, request_id: uuid.UUID, approve: bool) -> dict:
    forbid_delegated(ctx)
    require_role(ctx, "SME_ADMIN")
    org = ctx.effective_org_id
    with sess(db, ctx) as s:
        req = s.execute(text("select id, application_id, lender_org_id, requested_fields, status from access_requests where id = :i"), {"i": request_id}).first()
        if not req:
            raise NotFound("access request not found")
        if req.status != "PENDING":
            raise Conflict("this request was already decided", code="already_decided")
        app = _load_app(s, req.application_id)
        base = s.execute(text("select permitted_fields from disclosures where application_id = :a and level = 'summary' and revoked_at is null limit 1"), {"a": req.application_id}).first()
    if approve and (base is None or app.status != "PUBLISHED"):
        raise Conflict("the application is no longer shared", code="not_shared")
    values: dict = {}
    if approve:
        fields = list(dict.fromkeys([*base.permitted_fields, *req.requested_fields]))
        intel_fields, own_fields = F.split(fields)
        extract = _fetch_intelligence(intel, ctx, app.assessment_id, intel_fields)  # outside the transaction
        values = {**extract["fields"], **_marketplace_values(app, ctx, own_fields)}
    with sess(db, ctx) as s:
        locked = s.execute(text("select status from access_requests where id = :i for update"), {"i": request_id}).first()
        if locked.status != "PENDING":
            raise Conflict("this request was already decided", code="already_decided")
        s.execute(text("update access_requests set status = :st, decided_at = now() where id = :i"), {"st": "APPROVED" if approve else "DENIED", "i": request_id})
        if approve:
            profile_id = uuid.uuid4()
            s.execute(text("insert into published_profiles(id, application_id, sme_org_id, assessment_id, version, fields, as_of) values (:i, :a, :o, :as, 2, cast(:f as jsonb), :d)"),
                      {"i": profile_id, "a": app.id, "o": org, "as": app.assessment_id, "f": json.dumps(values), "d": extract_as_of(extract)})
            s.execute(text("insert into disclosures(id, application_id, sme_org_id, lender_org_id, level, purpose, permitted_fields, profile_id) values (:i, :a, :o, :l, 'full', 'application_review', :f, :p)"),
                      {"i": uuid.uuid4(), "a": app.id, "o": org, "l": req.lender_org_id, "f": list(values), "p": profile_id})
            emit(s, SVC, "marketplace.disclosure.granted", org, f"application/{app.id}", {"application_id": app.id, "sme_org_id": org, "lender_org_id": req.lender_org_id, "level": "full"})
        emit(s, SVC, "marketplace.access.decided", org, f"access/{request_id}",
             {"application_id": app.id, "request_id": request_id, "sme_org_id": org, "lender_org_id": req.lender_org_id, "decision": "APPROVED" if approve else "DENIED"})
        record_audit(s, SVC, ctx, "access.approved" if approve else "access.denied", f"access/{request_id}")
    return {"id": request_id, "status": "APPROVED" if approve else "DENIED"}


def extract_as_of(extract: dict) -> dt.date:
    return dt.date.fromisoformat(str(extract["as_of"]))


# --------------------------------------------------------------------------- dispute window
def dispute(db: Database, ctx: AccessContext, app_id: uuid.UUID) -> dict:
    """The SME objects to a payout confirmation within 14 days; Billing holds the fee (ADR-0013)."""
    forbid_delegated(ctx)
    require_role(ctx, "SME_ADMIN")
    org = ctx.effective_org_id
    with sess(db, ctx) as s:
        row = _load_app(s, app_id, lock=True)
        if row.status != "FUNDED":
            raise Conflict("only a loan confirmed as paid out can be disputed", code="not_funded")
        if row.disputed_at is not None:
            raise Conflict("this payout was already disputed", code="already_disputed")
        if row.dispute_until is None or dt.datetime.now(dt.timezone.utc) > row.dispute_until:
            raise Conflict("the 14-day dispute window has closed", code="dispute_window_closed")
        offer = s.execute(text("select id, lender_org_id, sme_quote_id, lender_quote_id from offers where application_id = :a and status = 'FUNDED'"), {"a": app_id}).first()
        s.execute(text("update applications set disputed_at = now() where id = :i"), {"i": app_id})
        emit(s, SVC, "marketplace.loan.disputed", org, f"application/{app_id}",
             {"offer_id": offer.id, "application_id": app_id, "sme_org_id": org, "lender_org_id": offer.lender_org_id,
              "quote_ids": [q for q in (offer.sme_quote_id, offer.lender_quote_id) if q]})
        record_audit(s, SVC, ctx, "loan.disputed", f"application/{app_id}")
    return {"application_id": app_id, "disputed": True}
