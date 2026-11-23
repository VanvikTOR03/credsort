"""Lender side: criteria, matches, offers with fee quotes, selection, payout confirmation (ADR-0011, ADR-0013, ADR-0021)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from decimal import Decimal

from sqlalchemy import text

from credsort_common.audit import record_audit
from credsort_common.db import Database, set_context
from credsort_common.errors import Conflict, Forbidden, NotFound, Unauthorized, Unprocessable, UpstreamHTTPError, UpstreamUnavailable
from credsort_common.events import emit
from credsort_common.idempotency import lookup_idempotent, run_idempotent
from credsort_common.money import q_amount
from credsort_common.security import AccessContext, RS256Verifier, forbid_delegated, require_org_type, require_role, require_verified

from .domain import cost, matching
from .domain.fields import CATALOGUE, MARKETPLACE_FIELDS
from .domain.lifecycle import APPLICATION, DISPUTE_WINDOW, OFFER, can_move
from .sessions import as_system, sess

SVC = "marketplace"
LENDER_ROLES = ("LENDER_ADMIN", "CREDIT_OFFICER")


def lender_only(ctx: AccessContext) -> None:
    require_org_type(ctx, "LENDER")
    require_role(ctx, *LENDER_ROLES)
    forbid_delegated(ctx)


# --------------------------------------------------------------------------- criteria
def get_criteria(db: Database, ctx: AccessContext) -> dict:
    lender_only(ctx)
    with sess(db, ctx) as s:
        row = s.execute(text("select version, criteria, created_at from lender_preferences order by version desc limit 1")).first()
    return {"version": row.version, "criteria": row.criteria, "created_at": row.created_at} if row else {"version": 0, "criteria": {}, "created_at": None}


def save_criteria(db: Database, ctx: AccessContext, criteria: dict) -> dict:
    lender_only(ctx)
    try:
        clean = matching.validate_criteria(criteria)
    except (matching.InvalidCriteria, ArithmeticError, ValueError) as exc:
        raise Unprocessable(str(exc), code="invalid_criteria") from exc
    with sess(db, ctx) as s:
        version = s.execute(text("select coalesce(max(version), 0) + 1 from lender_preferences")).scalar()
        s.execute(text("insert into lender_preferences(id, lender_org_id, version, criteria) values (:i, :o, :v, cast(:c as jsonb))"),
                  {"i": uuid.uuid4(), "o": ctx.org_id, "v": version, "c": json.dumps(clean)})
        record_audit(s, SVC, ctx, "criteria.saved", f"lender/{ctx.org_id}/criteria/{version}", org_id=ctx.org_id)
    return {"version": version, "criteria": clean}


# --------------------------------------------------------------------------- matches
def _visible(s, lender_org: uuid.UUID) -> list:
    """Applications this lender may see right now, with the best profile it is entitled to (a lender-specific `full` profile beats
    the shared summary one). The database policies already restrict these rows; the filters below repeat the rule on purpose."""
    rows = s.execute(text(
        "select a.id as application_id, a.status, a.published_at, d.level, d.permitted_fields, d.lender_org_id, p.fields, p.as_of "
        "from disclosures d join applications a on a.id = d.application_id join published_profiles p on p.id = d.profile_id "
        "where d.revoked_at is null and (d.lender_org_id is null or d.lender_org_id = :l) and a.status = 'PUBLISHED'"), {"l": lender_org}).all()
    best: dict = {}
    for r in rows:
        rank = (r.level == "full", r.lender_org_id is not None)
        if r.application_id not in best or rank > best[r.application_id][0]:
            best[r.application_id] = (rank, r)
    return [r for _, r in best.values()]


def matches(db: Database, ctx: AccessContext) -> dict:
    lender_only(ctx)
    require_verified(ctx)
    with sess(db, ctx) as s:
        pref = s.execute(text("select version, criteria from lender_preferences order by version desc limit 1")).first()
        criteria = pref.criteria if pref else {}
        found = []
        for r in _visible(s, ctx.org_id):
            m = matching.evaluate(criteria, r.fields)
            if m is not None:
                found.append((str(r.application_id), r.published_at.isoformat(), m, r))
        order = matching.rank([(a, p, m) for a, p, m, _ in found])
        by_id = {a: (m, r) for a, _, m, r in found}
        ids = [uuid.UUID(a) for a, _ in order]
        offers = {o.application_id: o for o in s.execute(text("select application_id, id, status from offers where application_id = any(:a) and lender_org_id = :l and status in ('SUBMITTED','SELECTED','FUNDED') "
                                                              "order by created_at desc"), {"a": ids, "l": ctx.org_id}).all()} if ids else {}
    items = []
    for rank_no, (aid, m) in enumerate(order, 1):
        _, r = by_id[aid]
        uid = uuid.UUID(aid)
        items.append({"rank": rank_no, "application_id": uid, "score": m.score, "level": r.level, "as_of": r.as_of, "published_at": r.published_at,
                      "fields": {f: v for f, v in r.fields.items() if v is not None}, "explanation": m.explanation,
                      "my_offer": {"id": offers[uid].id, "status": offers[uid].status} if uid in offers else None})
    return {"criteria_version": pref.version if pref else 0, "total": len(items), "items": items}


def lender_application(db: Database, ctx: AccessContext, app_id: uuid.UUID) -> dict:
    lender_only(ctx)
    require_verified(ctx)
    with sess(db, ctx) as s:
        mine = [r for r in _visible(s, ctx.org_id) if r.application_id == app_id]
        if not mine:
            raise NotFound("application not found")  # also covers revoked consent: nothing to see any more
        r = mine[0]
        pref = s.execute(text("select criteria from lender_preferences order by version desc limit 1")).first()
        m = matching.evaluate(pref.criteria if pref else {}, r.fields)
        offer = s.execute(text("select id, status, amount, rate, term_months from offers where application_id = :a and lender_org_id = :l order by created_at desc limit 1"), {"a": app_id, "l": ctx.org_id}).first()
        sme_org = _owner(s, app_id)  # elevated read of the owner id only, to attribute the audit record to the SME's stream
        record_audit(s, SVC, ctx, "application.viewed", f"application/{app_id}", org_id=sme_org)
    return {"application_id": app_id, "level": r.level, "as_of": r.as_of, "fields": {f: v for f, v in r.fields.items() if v is not None}, "labels": {f: CATALOGUE[f] for f in r.fields},
            "match": {"score": m.score, "explanation": m.explanation} if m else None, "my_offer": dict(offer._mapping) if offer else None}


def _owner(s, app_id):
    as_system(s)
    return s.execute(text("select sme_org_id from applications where id = :i"), {"i": app_id}).scalar()


# --------------------------------------------------------------------------- offers
def _quote(billing, *, subject: uuid.UUID, payer_org: uuid.UUID, payer_type: str, basis: Decimal) -> dict:
    try:
        return billing.post("/internal/v1/quotes", json={"action": "LOAN_FUNDED", "subject_id": str(subject), "payer_org_id": str(payer_org),
                                                          "payer_type": payer_type, "basis": format(basis, "f")})
    except (UpstreamUnavailable, UpstreamHTTPError) as exc:  # fail closed: never submit an offer whose fee could not be disclosed
        raise UpstreamUnavailable("fee information is temporarily unavailable; please try again in a moment", code="fees_unavailable") from exc


def submit_offer(db: Database, billing, ctx: AccessContext, app_id: uuid.UUID, terms: dict, idem_key: str | None) -> tuple[int, dict]:
    lender_only(ctx)
    require_verified(ctx)
    today = dt.date.today()
    if not (today < terms["valid_until"] <= today + dt.timedelta(days=60)):
        raise Unprocessable("an offer must be valid for between 1 and 60 days", code="invalid_validity")
    fingerprint = {"app": str(app_id), **{k: str(v) for k, v in terms.items()}}
    with sess(db, ctx) as s:
        replay = lookup_idempotent(s, ctx.org_id, idem_key, fingerprint)
        if replay:
            return replay  # a retried request neither asks Billing again nor creates a second offer
        mine = [r for r in _visible(s, ctx.org_id) if r.application_id == app_id]
        if not mine:
            raise NotFound("application not found")
        sme_org = _owner(s, app_id)
    offer_id = uuid.uuid4()
    amount = terms["amount"]
    sme_q = _quote(billing, subject=offer_id, payer_org=sme_org, payer_type="SME", basis=amount)  # remote calls BEFORE the transaction
    lender_q = _quote(billing, subject=offer_id, payer_org=ctx.org_id, payer_type="LENDER", basis=amount)
    with sess(db, ctx) as s:
        def action() -> tuple[int, dict]:
            visible = [r for r in _visible(s, ctx.org_id) if r.application_id == app_id]
            if not visible:
                raise NotFound("application not found")  # consent may have been revoked meanwhile
            if s.execute(text("select 1 from offers where application_id = :a and lender_org_id = :l and status = 'SUBMITTED'"), {"a": app_id, "l": ctx.org_id}).first():
                raise Conflict("withdraw your open offer before submitting a new one", code="offer_open")
            s.execute(text("insert into offers(id, application_id, sme_org_id, lender_org_id, lender_name, amount, rate, term_months, fees, repayment, collateral, valid_until, "
                           "sme_quote_id, sme_quote_token, sme_fee_amount, sme_fee_pricing, lender_quote_id, lender_quote_token, lender_fee_amount, lender_fee_pricing) "
                           "values (:i, :a, :s, :l, :n, :am, :r, :t, :f, :rp, :c, :v, :sq, :st, :sa, :sp, :lq, :lt, :la, :lp)"),
                      {"i": offer_id, "a": app_id, "s": sme_org, "l": ctx.org_id, "n": ctx.org_name, "am": amount, "r": terms["rate"], "t": terms["term_months"], "f": terms["fees"],
                       "rp": terms["repayment"], "c": terms.get("collateral"), "v": terms["valid_until"], "sq": sme_q["quote_id"], "st": sme_q["token"], "sa": Decimal(sme_q["amount"]),
                       "sp": sme_q["pricing"], "lq": lender_q["quote_id"], "lt": lender_q["token"], "la": Decimal(lender_q["amount"]), "lp": lender_q["pricing"]})
            profile = visible[0].fields
            s.execute(text("insert into benchmark_observations(id, category, amount_band, term_months, rate, lender_key) values (:i, :c, :b, :t, :r, :k)"),
                      {"i": uuid.uuid4(), "c": profile.get("assessment_category"), "b": _amount_band(amount), "t": terms["term_months"], "r": terms["rate"],
                       "k": hashlib.sha256(str(ctx.org_id).encode()).hexdigest()[:16]})
            emit(s, SVC, "marketplace.offer.submitted", sme_org, f"offer/{offer_id}", {"offer_id": offer_id, "application_id": app_id, "sme_org_id": sme_org, "lender_org_id": ctx.org_id})
            record_audit(s, SVC, ctx, "offer.submitted", f"offer/{offer_id}", org_id=sme_org)
            return 201, {"id": offer_id, "status": "SUBMITTED", "your_fee": {"amount": lender_q["amount"], "pricing": lender_q["pricing"]},
                         "sme_fee": {"amount": sme_q["amount"], "pricing": sme_q["pricing"]}}
        return run_idempotent(s, ctx.org_id, idem_key, fingerprint, action)


def _amount_band(amount: Decimal) -> str:
    return "<250k" if amount < 250_000 else "250k-1M" if amount < 1_000_000 else ">1M"


def withdraw_offer(db: Database, ctx: AccessContext, offer_id: uuid.UUID) -> dict:
    lender_only(ctx)
    with sess(db, ctx) as s:
        row = s.execute(text("select id, application_id, sme_org_id, status from offers where id = :i and lender_org_id = :l for update"), {"i": offer_id, "l": ctx.org_id}).first()
        if not row:
            raise NotFound("offer not found")
        if not can_move(OFFER, row.status, "WITHDRAWN"):
            raise Conflict(f"a {row.status.lower()} offer cannot be withdrawn", code="invalid_state")
        s.execute(text("update offers set status = 'WITHDRAWN' where id = :i"), {"i": offer_id})
        emit(s, SVC, "marketplace.offer.withdrawn", row.sme_org_id, f"offer/{offer_id}", {"offer_id": offer_id, "application_id": row.application_id, "sme_org_id": row.sme_org_id, "lender_org_id": ctx.org_id})
        record_audit(s, SVC, ctx, "offer.withdrawn", f"offer/{offer_id}", org_id=row.sme_org_id)
    return {"id": offer_id, "status": "WITHDRAWN"}


def _offer_out(r, view: str) -> dict:
    fee_amount, fee_pricing = (r.sme_fee_amount, r.sme_fee_pricing) if view == "sme" else (r.lender_fee_amount, r.lender_fee_pricing)
    c = cost.total_cost(r.amount, r.rate, r.term_months, r.repayment, r.fees, fee_amount if view == "sme" else Decimal(0))
    out = {"id": r.id, "application_id": r.application_id, "status": r.status, "lender_name": r.lender_name, "amount": r.amount, "rate": r.rate, "term_months": r.term_months,
           "fees": r.fees, "repayment": r.repayment, "collateral": r.collateral, "valid_until": r.valid_until, "created_at": r.created_at,
           "credsort_fee": {"amount": fee_amount, "pricing": fee_pricing}, "cost": c}
    return out


OFFER_COLS = ("id, application_id, lender_name, status, amount, rate, term_months, fees, repayment, collateral, valid_until, created_at, "
              "sme_fee_amount, sme_fee_pricing, lender_fee_amount, lender_fee_pricing")


def sme_offers(db: Database, ctx: AccessContext, app_id: uuid.UUID, sort: str) -> list[dict]:
    if ctx.org_type not in ("SME", "FIDUCIARY"):
        raise Forbidden("only the SME sees offers on its application", code="org_type_forbidden")
    with sess(db, ctx) as s:
        unlocked = s.execute(text("select unlocked_at is not null from applications where id = :a"), {"a": app_id}).scalar()
        rows = s.execute(text(f"select {OFFER_COLS} from offers where application_id = :a and status in ('SUBMITTED','SELECTED','FUNDED','CANCELLED') order by created_at"), {"a": app_id}).all()
    offers = [_offer_out(r, "sme") for r in rows]
    keys = {"total_cost": lambda o: (o["cost"]["total"], str(o["id"])), "rate": lambda o: (o["rate"], str(o["id"])),
            "amount": lambda o: (-o["amount"], str(o["id"]))}  # the SME's own key: never CredSort's revenue (ADR-0021)
    ordered = sorted(offers, key=keys.get(sort, keys["total_cost"]))
    for position, o in enumerate(ordered):
        o["unlocked"] = bool(unlocked)
        if not unlocked:  # the lender's identity is only revealed after the one-off unlock fee has been paid
            o["lender_name"] = f"Lender {chr(65 + position % 26)}"
    return ordered


def lender_offers(db: Database, ctx: AccessContext) -> list[dict]:
    lender_only(ctx)
    with sess(db, ctx) as s:
        rows = s.execute(text(f"select {OFFER_COLS} from offers where lender_org_id = :l order by created_at desc limit 100"), {"l": ctx.org_id}).all()
    return [_offer_out(r, "lender") for r in rows]


# --------------------------------------------------------------------------- selection (the ACID core)
def select_offer(db: Database, quotes, ctx: AccessContext, offer_id: uuid.UUID, idem_key: str | None) -> tuple[int, dict]:
    forbid_delegated(ctx)
    require_role(ctx, "SME_ADMIN")  # delegation never includes selecting offers (ADR-0019)
    org = ctx.effective_org_id
    with sess(db, ctx) as s:
        def action() -> tuple[int, dict]:
            offer = s.execute(text("select id, application_id, lender_org_id, status, valid_until, sme_quote_id, sme_quote_token, sme_fee_amount from offers where id = :i"), {"i": offer_id}).first()
            if not offer:
                raise NotFound("offer not found")
            app = s.execute(text("select id, status, sme_org_id, unlocked_at from applications where id = :a for update"), {"a": offer.application_id}).first()  # serialises concurrent selections
            if app.unlocked_at is None:
                raise Conflict("unlock the offers first to see who made them", code="not_unlocked")
            offer = s.execute(text("select id, application_id, lender_org_id, status, valid_until, sme_quote_id, sme_quote_token, sme_fee_amount from offers where id = :i for update"), {"i": offer_id}).first()
            if not can_move(APPLICATION, app.status, "OFFER_SELECTED") or not can_move(OFFER, offer.status, "SELECTED"):
                raise Conflict("this offer can no longer be selected", code="offer_unavailable")
            if offer.valid_until < dt.date.today():
                raise Conflict("this offer has expired", code="offer_expired")
            try:  # the fee shown when comparing is locked in: verified locally, no Billing call needed now (ADR-0013)
                claims = quotes.verify(offer.sme_quote_token)
            except Unauthorized as exc:
                raise Conflict("the fee quote for this offer is no longer valid; ask the lender to resubmit", code="quote_invalid") from exc
            if (claims["act"], claims["sub"], claims["payer"], claims["qid"], Decimal(claims["amount"])) != ("LOAN_FUNDED", str(offer.id), str(app.sme_org_id), str(offer.sme_quote_id), offer.sme_fee_amount):
                raise Conflict("the fee quote does not match this offer", code="quote_mismatch")
            s.execute(text("update offers set status = 'REJECTED' where application_id = :a and status = 'SUBMITTED' and id <> :i"), {"a": app.id, "i": offer_id})
            others = [r.lender_org_id for r in s.execute(text("select lender_org_id from offers where application_id = :a and status = 'REJECTED'"), {"a": app.id}).all()]
            s.execute(text("update offers set status = 'SELECTED' where id = :i"), {"i": offer_id})  # the partial unique index is the second guard
            s.execute(text("update applications set status = 'OFFER_SELECTED', selected_offer_id = :i, selected_at = now() where id = :a"), {"i": offer_id, "a": app.id})
            emit(s, SVC, "marketplace.offer.selected", org, f"offer/{offer_id}", {"offer_id": offer_id, "application_id": app.id, "sme_org_id": org,
                                                                                    "lender_org_id": offer.lender_org_id, "other_lender_org_ids": others})
            record_audit(s, SVC, ctx, "offer.selected", f"offer/{offer_id}")
            return 200, {"offer_id": offer_id, "application_id": app.id, "status": "SELECTED",
                         "note": "Complete the loan directly with the lender. CredSort charges its fee only once the lender confirms the payout."}
        return run_idempotent(s, org, idem_key, {"offer": str(offer_id)}, action)


# --------------------------------------------------------------------------- payout confirmation (ADR-0013: the fee becomes payable now)
def _selected_offer_of_lender(s, ctx, offer_id):
    row = s.execute(text("select id, application_id, sme_org_id, lender_org_id, status, sme_quote_id, lender_quote_id from offers where id = :i and lender_org_id = :l for update"),
                    {"i": offer_id, "l": ctx.org_id}).first()
    if not row:
        raise NotFound("offer not found")
    return row


def confirm_payout(db: Database, ctx: AccessContext, offer_id: uuid.UUID, idem_key: str | None) -> tuple[int, dict]:
    lender_only(ctx)
    require_verified(ctx)
    with sess(db, ctx) as s:
        def action() -> tuple[int, dict]:
            offer = _selected_offer_of_lender(s, ctx, offer_id)
            if not can_move(OFFER, offer.status, "FUNDED"):  # a loan can become FUNDED once, so a fee can never be triggered twice
                raise Conflict("only a selected offer can be confirmed as paid out, and only once", code="invalid_state")
            as_system(s)  # this lender may trigger exactly this transition on ITS selected offer; the application row belongs to the SME
            s.execute(text("update offers set status = 'FUNDED' where id = :i"), {"i": offer_id})
            s.execute(text("update applications set status = 'FUNDED', funded_at = now(), dispute_until = now() + make_interval(secs => :w), closed_at = now() where id = :a"),
                      {"a": offer.application_id, "w": DISPUTE_WINDOW.total_seconds()})
            emit(s, SVC, "marketplace.loan.funded", offer.sme_org_id, f"offer/{offer_id}",
                 {"offer_id": offer_id, "application_id": offer.application_id, "sme_org_id": offer.sme_org_id, "lender_org_id": offer.lender_org_id,
                  "quote_ids": [q for q in (offer.sme_quote_id, offer.lender_quote_id) if q]})
            record_audit(s, SVC, ctx, "loan.funded", f"offer/{offer_id}", org_id=offer.sme_org_id)
            return 200, {"offer_id": offer_id, "status": "FUNDED", "dispute_days": 14}
        return run_idempotent(s, ctx.org_id, idem_key, {"offer": str(offer_id), "op": "payout"}, action)


def cancel_loan(db: Database, ctx: AccessContext, offer_id: uuid.UUID) -> dict:
    lender_only(ctx)
    with sess(db, ctx) as s:
        offer = _selected_offer_of_lender(s, ctx, offer_id)
        if not can_move(OFFER, offer.status, "CANCELLED"):
            raise Conflict("only a selected, not yet paid-out loan can be cancelled", code="invalid_state")
        as_system(s)
        s.execute(text("update offers set status = 'CANCELLED' where id = :i"), {"i": offer_id})
        s.execute(text("update applications set status = 'CANCELLED', closed_at = now() where id = :a"), {"a": offer.application_id})
        emit(s, SVC, "marketplace.loan.cancelled", offer.sme_org_id, f"offer/{offer_id}",
             {"offer_id": offer_id, "application_id": offer.application_id, "sme_org_id": offer.sme_org_id, "lender_org_id": offer.lender_org_id,
              "quote_ids": [q for q in (offer.sme_quote_id, offer.lender_quote_id) if q]})
        record_audit(s, SVC, ctx, "loan.cancelled", f"offer/{offer_id}", org_id=offer.sme_org_id)
    return {"offer_id": offer_id, "status": "CANCELLED"}


# --------------------------------------------------------------------------- benchmark (ADR-0022: anonymised, k >= 5 offers from >= 3 lenders)
def benchmark(db: Database) -> dict:
    with db.session(None, "SYSTEM") as s:
        rows = s.execute(text("select coalesce(category, 'n/a') as category, amount_band, count(*) as offers, count(distinct lender_key) as lenders, "
                              "avg(rate) as avg_rate, min(rate) as min_rate, max(rate) as max_rate from benchmark_observations "
                              "group by 1, 2 having count(*) >= 5 and count(distinct lender_key) >= 3 order by 1, 2")).all()
    return {"min_offers": 5, "min_lenders": 3, "illustrative": True, "groups": [{**dict(r._mapping), "avg_rate": q_amount(r.avg_rate)} for r in rows],
            "note": "Illustrative aggregates from offers on CredSort. Shown only for groups with at least 5 offers from at least 3 lenders."}


# --------------------------------------------------------------------------- matcher (consumer, best-effort notifications)
def notify_matches(session, event) -> None:
    """Runs after publication: tells matching lenders (by id only). The matching itself is recomputed live on every query."""
    set_context(session, None, "SYSTEM")
    app_id = event["data"]["application_id"]
    discl = session.execute(text("select d.lender_org_id, d.profile_id, p.fields from disclosures d join published_profiles p on p.id = d.profile_id "
                                 "where d.application_id = :a and d.revoked_at is null"), {"a": app_id}).all()
    prefs = session.execute(text("select distinct on (lender_org_id) lender_org_id, criteria from lender_preferences order by lender_org_id, version desc")).all()
    hits = sorted({p.lender_org_id for p in prefs for d in discl if (d.lender_org_id is None or d.lender_org_id == p.lender_org_id)
                   and matching.evaluate(p.criteria, d.fields) is not None}, key=str)
    if hits:
        emit(session, SVC, "marketplace.application.matched", event["credsortorgid"], f"application/{app_id}",
             {"application_id": app_id, "sme_org_id": event["credsortorgid"], "lender_org_ids": list(hits)})


def mark_unlocked(session, event) -> None:
    """The company paid the one-off unlock fee (Billing): lender identities become visible on that application. Idempotent."""
    set_context(session, None, "SYSTEM")
    d = event["data"]
    changed = session.execute(text("update applications set unlocked_at = now() where id = :a and sme_org_id = :o and unlocked_at is null returning id"),
                              {"a": d["application_id"], "o": d["org_id"]}).first()
    if changed:
        record_audit(session, SVC, None, "offers.unlocked", f"application/{d['application_id']}", org_id=d["org_id"])


def delete_org_data(session, org_id) -> None:
    from credsort_common.lifecycle import finish_deletion
    as_system(session)
    session.execute(text("delete from offers where sme_org_id = :o or lender_org_id = :o"), {"o": org_id})
    session.execute(text("delete from access_requests where sme_org_id = :o or lender_org_id = :o"), {"o": org_id})
    session.execute(text("delete from lender_preferences where lender_org_id = :o"), {"o": org_id})
    session.execute(text("delete from applications where sme_org_id = :o"), {"o": org_id})  # cascades profiles and disclosures
    finish_deletion(session, SVC, org_id)
