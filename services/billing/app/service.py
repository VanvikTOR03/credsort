"""Billing use cases (ADR-0013): price books, signed quotes, charges exactly as quoted, referral shares, entitlements."""
from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import text

from credsort_common.audit import record_audit
from credsort_common.db import Database, set_context
from credsort_common.errors import Conflict, NotFound, Unprocessable
from credsort_common.events import emit
from credsort_common.lifecycle import finish_deletion
from credsort_common.money import D, q_amount
from credsort_common.security import AccessContext, KeyStore

from .domain.fees import DEFAULT_ENTITLEMENTS, TRIGGERS, Rule, quote_amount

SVC = "billing"
QUOTE_TTL = dt.timedelta(days=90)
DISPUTE_WINDOW = dt.timedelta(days=14)
QUOTE_ISS, QUOTE_AUD = "credsort-billing", "credsort-quotes"


# --------------------------------------------------------------------------- price books
def _rules(rows) -> list[Rule]:
    return [Rule(r.code, r.payer, r.trigger, r.calculator, r.amount, r.percent, r.min_amount, r.cap_amount) for r in rows]


def active_book(s):
    return s.execute(text("select id, version, is_placeholder, referral_percent from price_books where status = 'ACTIVE' "
                          "and (effective_from is null or effective_from <= current_date) order by version desc limit 1")).first()


def create_price_book(db: Database, ctx: AccessContext, rules: list[dict], placeholder: bool) -> dict:
    with db.session(None, "PLATFORM") as s:
        version = (s.execute(text("select coalesce(max(version), 0) + 1 from price_books")).scalar())
        pid = uuid.uuid4()
        s.execute(text("insert into price_books(id, version, is_placeholder) values (:i, :v, :p)"), {"i": pid, "v": version, "p": placeholder})
        for r in rules:
            s.execute(text("insert into fee_rules(id, price_book_id, code, payer, trigger, calculator, amount, percent, min_amount, cap_amount) "
                           "values (:i, :b, :c, :p, :t, :k, :a, :pc, :mn, :cp)"),
                      {"i": uuid.uuid4(), "b": pid, "c": r["code"], "p": r["payer"], "t": r["trigger"], "k": r["calculator"], "a": r.get("amount"),
                       "pc": r.get("percent"), "mn": r.get("min_amount"), "cp": r.get("cap_amount")})
        record_audit(s, SVC, ctx, "price_book.created", f"price_book/{pid}", org_id=ctx.org_id)
    return {"id": pid, "version": version, "status": "DRAFT"}


def activate_price_book(db: Database, ctx: AccessContext, book_id: uuid.UUID, effective_from: dt.date | None) -> dict:
    with db.session(None, "PLATFORM") as s:
        row = s.execute(text("select version, status from price_books where id = :i for update"), {"i": book_id}).first()
        if not row:
            raise NotFound("price book not found")
        if row.status != "DRAFT":
            raise Conflict("only a draft price book can be activated", code="not_a_draft")
        s.execute(text("update price_books set status = 'SUPERSEDED' where status = 'ACTIVE'"))
        s.execute(text("update price_books set status = 'ACTIVE', effective_from = :e, activated_at = now() where id = :i"), {"e": effective_from or dt.date.today(), "i": book_id})
        emit(s, SVC, "billing.price_book.activated", ctx.org_id, f"price_book/{book_id}", {"price_book_id": book_id, "version": row.version})
        record_audit(s, SVC, ctx, "price_book.activated", f"price_book/{book_id}", org_id=ctx.org_id)
    return {"id": book_id, "version": row.version, "status": "ACTIVE"}


def list_price_books(db: Database) -> list[dict]:
    with db.session(None, "PLATFORM") as s:
        books = s.execute(text("select id, version, status, effective_from, is_placeholder, referral_percent from price_books order by version desc")).all()
        out = []
        for b in books:
            rules = s.execute(text("select code, payer, trigger, calculator, amount, percent, min_amount, cap_amount from fee_rules where price_book_id = :i order by code"), {"i": b.id}).all()
            out.append({**b._mapping, "rules": [dict(r._mapping) for r in rules]})
    return out


def public_pricing(db: Database) -> dict:
    """Fee disclosure shown to every organization before it commits to anything."""
    with db.session(None, "NONE") as s:
        book = active_book(s)
        if not book:
            return {"status": "NONE", "placeholder": False, "rules": []}
        rules = s.execute(text("select code, payer, trigger, calculator, amount, percent, min_amount, cap_amount from fee_rules where price_book_id = :i"), {"i": book.id}).all()
    return {"status": "ACTIVE", "version": book.version, "placeholder": book.is_placeholder, "rules": [dict(r._mapping) for r in rules]}


# --------------------------------------------------------------------------- quotes
def issue_quote(db: Database, keystore: KeyStore, *, action: str, subject_id: uuid.UUID, payer_org_id: uuid.UUID, payer_type: str, basis: Decimal) -> dict:
    if action not in TRIGGERS:
        raise Unprocessable(f"unknown fee trigger {action}", code="unknown_trigger")
    if basis <= 0:
        raise Unprocessable("basis must be positive", code="invalid_basis")
    with db.session(payer_org_id, "EVENT") as s:
        book = active_book(s)
        rules: list[Rule] = []
        if book:
            rules = _rules(s.execute(text("select code, payer, trigger, calculator, amount, percent, min_amount, cap_amount from fee_rules "
                                          "where price_book_id = :b and trigger = :t and payer = :p"), {"b": book.id, "t": action, "p": payer_type}).all())
        amount = quote_amount(rules, basis) if rules else Decimal(0)
        pricing = "PRICED" if rules else "UNPRICED"
        qid = uuid.uuid4()
        now = dt.datetime.now(dt.timezone.utc)
        expires = now + QUOTE_TTL
        s.execute(text("insert into quotes(id, org_id, payer_type, action, subject_id, basis, amount, pricing, price_book_version, rule_codes, expires_at) "
                       "values (:i, :o, :pt, :a, :su, :b, :am, :pr, :v, :rc, :e)"),
                  {"i": qid, "o": payer_org_id, "pt": payer_type, "a": action, "su": subject_id, "b": basis, "am": amount, "pr": pricing,
                   "v": book.version if book else None, "rc": [r.code for r in rules], "e": expires})
    claims = {"iss": QUOTE_ISS, "aud": QUOTE_AUD, "iat": int(now.timestamp()), "exp": int(expires.timestamp()), "qid": str(qid), "act": action,
              "sub": str(subject_id), "payer": str(payer_org_id), "ptype": payer_type, "basis": format(q_amount(basis), "f"), "amount": format(amount, "f"),
              "ccy": "CHF", "pricing": pricing, "pbv": book.version if book else None}
    return {"quote_id": qid, "token": keystore.sign(claims), "amount": amount, "currency": "CHF", "pricing": pricing,
            "price_book_version": book.version if book else None, "expires_at": expires, "rule_codes": [r.code for r in rules]}


# --------------------------------------------------------------------------- charges (event handlers act on Billing's own ledger)
def _as_billing(session) -> None:
    set_context(session, None, "SYSTEM")


def _held(session, event, org_id, quote_id, reason: str) -> None:
    session.execute(text("insert into held_events(id, org_id, source_event_id, reason_code) values (:i, :o, :e, :r)"),
                    {"i": uuid.uuid4(), "o": org_id, "e": event["id"], "r": reason})
    emit(session, SVC, "billing.charge.held", org_id or uuid.UUID(int=0), f"quote/{quote_id}",
         {"org_id": org_id, "quote_id": quote_id, "reason_code": reason, "source_event_id": event["id"]})


def record_charges(session, event) -> None:
    """The lender confirmed the payout: charge exactly what was quoted (ADR-0013). Idempotent per quote."""
    d = event["data"]
    _as_billing(session)
    for qid in d["quote_ids"]:
        q = session.execute(text("select id, org_id, payer_type, subject_id, basis, amount, pricing, price_book_version from quotes where id = :i"), {"i": qid}).first()
        if q is None:
            _held(session, event, None, qid, "UNKNOWN_QUOTE")
            continue
        if str(q.subject_id) != d["offer_id"] or str(q.org_id) not in (d["sme_org_id"], d["lender_org_id"]):
            _held(session, event, q.org_id, qid, "SUBJECT_MISMATCH")
            continue
        if session.execute(text("select 1 from fee_charges where quote_id = :q"), {"q": qid}).first():
            continue  # second layer of duplicate protection: one charge per quote, whatever events arrive
        status = "RECORDED" if q.pricing == "PRICED" and q.amount > 0 else "NO_FEE"
        charge_id = uuid.uuid4()
        session.execute(text("insert into fee_charges(id, org_id, quote_id, offer_id, application_id, basis, amount, price_book_version, status, payable_after) "
                             "values (:i, :o, :q, :of, :ap, :b, :a, :v, :s, :pa)"),
                        {"i": charge_id, "o": q.org_id, "q": qid, "of": d["offer_id"], "ap": d["application_id"], "b": q.basis, "a": q.amount,
                         "v": q.price_book_version, "s": status, "pa": dt.datetime.now(dt.timezone.utc) + DISPUTE_WINDOW if status == "RECORDED" else None})
        if status == "RECORDED" and q.payer_type == "SME":
            ref = session.execute(text("select referred_by_org_id from referrals where org_id = :o"), {"o": q.org_id}).first()
            book = session.execute(text("select referral_percent from price_books where version = :v"), {"v": q.price_book_version}).first()
            if ref and book:
                share = q_amount(q.amount * book.referral_percent / 100)
                session.execute(text("insert into referral_shares(id, charge_id, org_id, fiduciary_org_id, percent, amount) values (:i, :c, :o, :f, :p, :a)"),
                                {"i": uuid.uuid4(), "c": charge_id, "o": q.org_id, "f": ref.referred_by_org_id, "p": book.referral_percent, "a": share})
        emit(session, SVC, "billing.charge.recorded", q.org_id, f"charge/{charge_id}", {"charge_id": charge_id, "org_id": q.org_id, "quote_id": qid})
        record_audit(session, SVC, None, "charge.recorded", f"charge/{charge_id}", org_id=q.org_id)


def _change_status(session, event, allowed_from: tuple[str, ...], new_status: str) -> None:
    _as_billing(session)
    for qid in event["data"]["quote_ids"]:
        row = session.execute(text("update fee_charges set status = :n, updated_at = now() where quote_id = :q and status = any(:f) returning id, org_id"),
                              {"n": new_status, "q": qid, "f": list(allowed_from)}).first()
        if row:
            emit(session, SVC, "billing.charge.status_changed", row.org_id, f"charge/{row.id}", {"charge_id": row.id, "org_id": row.org_id, "status": new_status}, version=2)
            record_audit(session, SVC, None, f"charge.{new_status.lower()}", f"charge/{row.id}", org_id=row.org_id)


def hold_charges(session, event) -> None:
    _change_status(session, event, ("RECORDED",), "HELD")


def cancel_charges(session, event) -> None:
    _change_status(session, event, ("RECORDED", "HELD"), "CANCELLED")


def store_referral(session, event) -> None:
    d = event["data"]
    if d.get("referred_by_org_id"):
        _as_billing(session)
        session.execute(text("insert into referrals(org_id, referred_by_org_id) values (:o, :r) on conflict do nothing"), {"o": d["org_id"], "r": d["referred_by_org_id"]})


def admin_resolve(db: Database, ctx: AccessContext, charge_id: uuid.UUID, outcome: str) -> dict:
    new = {"release": "RECORDED", "waive": "WAIVED"}[outcome]
    with db.session(None, "PLATFORM") as s:
        row = s.execute(text("update fee_charges set status = :n, updated_at = now() where id = :i and status = 'HELD' returning id, org_id"), {"n": new, "i": charge_id}).first()
        if not row:
            raise Conflict("only held charges can be resolved", code="not_held")
        emit(s, SVC, "billing.charge.status_changed", row.org_id, f"charge/{charge_id}", {"charge_id": charge_id, "org_id": row.org_id, "status": new}, version=3)
        record_audit(s, SVC, ctx, f"charge.{outcome}d", f"charge/{charge_id}", org_id=row.org_id)
    return {"id": charge_id, "status": new}


def list_charges(db: Database, ctx: AccessContext) -> list[dict]:
    with db.session(ctx.org_id) as s:
        rows = s.execute(text("select id, offer_id, application_id, basis, amount, price_book_version, status, payable_after, created_at from fee_charges order by created_at desc limit 50")).all()
    return [dict(r._mapping) for r in rows]


def admin_charges(db: Database, status: str | None) -> list[dict]:
    with db.session(None, "PLATFORM") as s:
        rows = s.execute(text("select id, org_id, offer_id, application_id, basis, amount, status, payable_after, created_at from fee_charges "
                              "where cast(:s as text) is null or status = cast(:s as text) order by created_at desc limit 100"), {"s": status}).all()
    return [dict(r._mapping) for r in rows]


# --------------------------------------------------------------------------- entitlements
def entitlements(db: Database, org_id: uuid.UUID) -> list[str]:
    with db.session(org_id, "EVENT") as s:
        row = s.execute(text("select entitlements from entitlement_overrides where org_id = :o"), {"o": org_id}).first()
    return list(row.entitlements) if row else list(DEFAULT_ENTITLEMENTS)


def set_entitlements(db: Database, ctx: AccessContext, org_id: uuid.UUID, values: list[str]) -> dict:
    bad = set(values) - set(DEFAULT_ENTITLEMENTS)
    if bad:
        raise Unprocessable(f"unknown entitlements {sorted(bad)}", code="unknown_entitlement")
    with db.session(None, "PLATFORM") as s:
        s.execute(text("insert into entitlement_overrides(org_id, entitlements) values (:o, :e) on conflict (org_id) do update set entitlements = excluded.entitlements, updated_at = now()"),
                  {"o": org_id, "e": values})
        emit(s, SVC, "billing.entitlements.changed", org_id, f"organization/{org_id}", {"org_id": org_id, "entitlements": values})
        record_audit(s, SVC, ctx, "entitlements.changed", f"organization/{org_id}", org_id=org_id)
    return {"org_id": org_id, "entitlements": values}


def delete_org_data(session, org_id) -> None:
    """Invoices and charges are retained for the legal retention period (ADR-0031); everything else is removed."""
    _as_billing(session)
    for table in ("referrals", "entitlement_overrides", "held_events"):
        session.execute(text(f"delete from {table} where org_id = :o"), {"o": org_id})
    session.execute(text("delete from quotes q where q.org_id = :o and not exists (select 1 from fee_charges c where c.quote_id = q.id)"), {"o": org_id})
    finish_deletion(session, SVC, org_id)
