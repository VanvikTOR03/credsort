"""Accounting Integration use cases (ADR-0002, ADR-0005, ADR-0010)."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from credsort_common.audit import record_audit
from credsort_common.config import is_prod
from credsort_common.db import Database
from credsort_common.errors import Conflict, Forbidden, NotFound, Unprocessable
from credsort_common.events import emit
from credsort_common.idempotency import run_idempotent
from credsort_common.lifecycle import finish_deletion
from credsort_common.security import AccessContext

SVC = "accounting"


def _job(r) -> dict:
    return {"id": r.id, "connection_id": r.connection_id, "status": r.status, "progress": r.progress, "failure_reason": r.failure_reason,
            "batch_id": r.batch_id, "created_at": r.created_at, "finished_at": r.finished_at}


def create_connection(db: Database, ctx: AccessContext, source_type: str, dataset: str) -> dict:
    if source_type == "SYNTHETIC" and is_prod():
        raise Forbidden("synthetic data sources are disabled in production", code="synthetic_disabled")
    org = ctx.effective_org_id
    cid = uuid.uuid4()
    with db.session(org) as s:
        s.execute(text("insert into data_connections(id, org_id, source_type, config) values (:i, :o, :t, cast(:c as jsonb))"),
                  {"i": cid, "o": org, "t": source_type, "c": '{"dataset": "%s"}' % dataset if source_type == "SYNTHETIC" else "{}"})
        record_audit(s, SVC, ctx, "connection.created", f"connection/{cid}")
    return {"id": cid, "source_type": source_type, "status": "ACTIVE", "dataset": dataset if source_type == "SYNTHETIC" else None}


def list_connections(db: Database, ctx: AccessContext) -> list[dict]:
    with db.session(ctx.effective_org_id) as s:
        rows = s.execute(text("select c.id, c.source_type, c.status, c.config->>'dataset' as dataset, c.created_at, "
                              "(select max(b.period_end) from import_batches b where b.connection_id = c.id) as last_period_end, "
                              "(select max(j.finished_at) from import_jobs j where j.connection_id = c.id and j.status = 'COMPLETED') as last_import_at "
                              "from data_connections c where c.status = 'ACTIVE' order by c.created_at")).all()
    return [dict(r._mapping) for r in rows]


def revoke_connection(db: Database, ctx: AccessContext, connection_id: uuid.UUID) -> None:
    with db.session(ctx.effective_org_id) as s:
        row = s.execute(text("update data_connections set status = 'REVOKED', token_enc = null where id = :i and status = 'ACTIVE' returning id"),
                        {"i": connection_id}).first()
        if not row:
            raise NotFound("connection not found")
        emit(s, SVC, "accounting.connection.revoked", ctx.effective_org_id, f"connection/{connection_id}", {"org_id": ctx.effective_org_id, "connection_id": connection_id})
        record_audit(s, SVC, ctx, "connection.revoked", f"connection/{connection_id}")


def start_import(db: Database, ctx: AccessContext, connection_id: uuid.UUID, idem_key: str | None) -> tuple[int, dict]:
    org = ctx.effective_org_id
    with db.session(org) as s:
        def action() -> tuple[int, dict]:
            conn = s.execute(text("select id from data_connections where id = :i and status = 'ACTIVE'"), {"i": connection_id}).first()
            if not conn:
                raise NotFound("connection not found")
            jid = uuid.uuid4()
            try:
                with s.begin_nested():
                    s.execute(text("insert into import_jobs(id, org_id, connection_id) values (:i, :o, :c)"), {"i": jid, "o": org, "c": connection_id})
            except IntegrityError as exc:
                raise Conflict("an import is already running for this connection", code="import_in_progress") from exc
            record_audit(s, SVC, ctx, "import.requested", f"job/{jid}")
            return 202, {"id": jid, "status": "PENDING", "location": f"/v1/import-jobs/{jid}"}
        return run_idempotent(s, org, idem_key, {"connection_id": str(connection_id)}, action)


def get_job(db: Database, ctx: AccessContext, job_id: uuid.UUID) -> dict:
    with db.session(ctx.effective_org_id) as s:
        r = s.execute(text("select id, connection_id, status, progress, failure_reason, batch_id, created_at, finished_at from import_jobs where id = :i"), {"i": job_id}).first()
    if not r:
        raise NotFound("import job not found")
    return _job(r)


def list_jobs(db: Database, ctx: AccessContext, connection_id: uuid.UUID | None) -> list[dict]:
    with db.session(ctx.effective_org_id) as s:
        rows = s.execute(text("select id, connection_id, status, progress, failure_reason, batch_id, created_at, finished_at from import_jobs "
                              "where (cast(:c as uuid) is null or connection_id = cast(:c as uuid)) order by created_at desc limit 20"), {"c": connection_id}).all()
    return [_job(r) for r in rows]


def ledger_for_batch(db: Database, org_id: uuid.UUID, batch_id: uuid.UUID) -> dict:
    """Claim-check endpoint for Financial Intelligence: only the owning organization's batch is visible (RLS)."""
    with db.session(org_id, "EVENT") as s:
        b = s.execute(text("select id, org_id, source_type, period_start, period_end, content_hash, normalizer_version, validator_version "
                           "from import_batches where id = :i"), {"i": batch_id}).first()
        if not b:
            raise NotFound("batch not found")  # also covers deleted organizations (no resurrection of data)
        accounts = s.execute(text("select code, name from canonical_accounts where batch_id = :i order by code"), {"i": batch_id}).all()
        opening = s.execute(text("select account_code, amount from opening_balances where batch_id = :i order by account_code"), {"i": batch_id}).all()
        entries = s.execute(text("select entry_date, debit_account, credit_account, amount, reference from journal_entries where batch_id = :i order by entry_date, id"), {"i": batch_id}).all()
        record_audit(s, SVC, None, "ledger.read", f"batch/{batch_id}", org_id=org_id)
    return {"batch_id": b.id, "org_id": b.org_id, "source_type": b.source_type, "period_start": b.period_start, "period_end": b.period_end,
            "content_hash": b.content_hash, "normalizer_version": b.normalizer_version, "validator_version": b.validator_version,
            "accounts": [{"code": a.code, "name": a.name} for a in accounts],
            "opening": [{"account_code": o.account_code, "amount": o.amount} for o in opening],
            "entries": [{"date": e.entry_date, "debit_account": e.debit_account, "credit_account": e.credit_account, "amount": e.amount, "reference": e.reference} for e in entries]}


def delete_org_data(session, org_id) -> None:
    for table in ("journal_entries", "opening_balances", "canonical_accounts", "import_jobs", "import_batches", "data_connections"):
        session.execute(text(f"delete from {table} where org_id = :o"), {"o": org_id})
    finish_deletion(session, SVC, org_id)
