"""Import workers (ADR-0005, ADR-0010): lease jobs, fetch outside transactions, write atomically, emit through the outbox."""
from __future__ import annotations

import logging
import threading
import uuid
import time
from datetime import date, timedelta

from sqlalchemy import text

from credsort_common.audit import record_audit
from credsort_common.db import Database
from credsort_common.events import emit
from credsort_common.reqctx import new_traceparent, set_request

from .domain.ledger import NORMALIZER_VERSION, VALIDATOR_VERSION, content_hash, validate
from .plugins.base import ProviderError
from .plugins.registry import provider_for

SVC = "accounting"
LEASE = timedelta(minutes=5)
MAX_ATTEMPTS = 3
log = logging.getLogger("credsort.accounting.worker")


def claim_next(db: Database):
    """Claim a PENDING job, or a RUNNING job whose lease expired (crashed worker)."""
    with db.system() as s:
        job = s.execute(text(
            "select id, org_id, connection_id, attempts from import_jobs "
            "where status = 'PENDING' or (status = 'RUNNING' and locked_until < now()) "
            "order by created_at limit 1 for update skip locked")).first()
        if not job:
            return None
        if job.attempts >= MAX_ATTEMPTS:
            _fail(s, job, "MAX_ATTEMPTS")
            return None
        s.execute(text("update import_jobs set status = 'RUNNING', attempts = attempts + 1, locked_until = now() + make_interval(secs => :l), "
                       "started_at = coalesce(started_at, now()), progress = 10 where id = :i"), {"l": LEASE.total_seconds(), "i": job.id})
        return job


def _fail(s, job, code: str) -> None:
    s.execute(text("update import_jobs set status = 'FAILED', failure_reason = :r, finished_at = now(), locked_until = null where id = :i"),
              {"r": code, "i": job.id})
    emit(s, SVC, "accounting.import.failed", job.org_id, f"job/{job.id}", {"org_id": job.org_id, "job_id": job.id, "reason_code": code})
    record_audit(s, SVC, None, "import.failed", f"job/{job.id}", org_id=job.org_id)


def run_job(db: Database, job, as_of: date | None = None) -> str:
    """Executes one claimed job. Returns COMPLETED, REUSED (identical data) or the failure code."""
    as_of = as_of or date.today()
    set_request(f"job-{str(job.id)[:8]}", new_traceparent())
    with db.session(job.org_id, "EVENT") as s:
        conn = s.execute(text("select source_type, config, token_enc, status from data_connections where id = :c"), {"c": job.connection_id}).first()
    if conn is None or conn.status != "ACTIVE":
        with db.system() as s:
            _fail(s, job, "CONNECTION_REVOKED")
        return "CONNECTION_REVOKED"
    try:  # external call: NOT inside a transaction (ADR-0007)
        ledger = provider_for(conn.source_type).fetch({"config": conn.config, "token_enc": conn.token_enc}, as_of)
    except ProviderError as exc:
        with db.system() as s:
            _fail(s, job, exc.code)
        return exc.code
    except Exception:
        log.exception("import provider crashed", extra={"job_id": str(job.id)})
        with db.system() as s:
            _fail(s, job, "PROVIDER_ERROR")
        return "PROVIDER_ERROR"
    issues = [i for i in validate(ledger) if i.blocking]
    if issues:
        code = f"VALIDATION_{issues[0].code}"
        with db.system() as s:
            _fail(s, job, code)
        return code
    digest = content_hash(ledger)
    with db.session(job.org_id, "EVENT") as s:
        existing = s.execute(text("select id from import_batches where connection_id = :c and period_start = :ps and period_end = :pe and "
                                  "content_hash = :h and normalizer_version = :n"),
                             {"c": job.connection_id, "ps": ledger.period_start, "pe": ledger.period_end, "h": digest, "n": NORMALIZER_VERSION}).first()
        if existing:  # identical data: complete without a new batch or event (ADR-0010)
            s.execute(text("update import_jobs set status = 'COMPLETED', progress = 100, batch_id = :b, finished_at = now(), locked_until = null where id = :i"),
                      {"b": existing.id, "i": job.id})
            return "REUSED"
        batch_id = uuid.uuid4()
        s.execute(text("insert into import_batches(id, org_id, connection_id, source_type, period_start, period_end, content_hash, normalizer_version, validator_version) "
                       "values (:i, :o, :c, :t, :ps, :pe, :h, :n, :v)"),
                  {"i": batch_id, "o": job.org_id, "c": job.connection_id, "t": ledger.source_type, "ps": ledger.period_start, "pe": ledger.period_end,
                   "h": digest, "n": NORMALIZER_VERSION, "v": VALIDATOR_VERSION})
        s.execute(text("insert into canonical_accounts(batch_id, org_id, code, name) values (:b, :o, :c, :n)"),
                  [{"b": batch_id, "o": job.org_id, "c": c, "n": n} for c, n in ledger.accounts.items()])
        if ledger.opening:
            s.execute(text("insert into opening_balances(batch_id, org_id, account_code, amount) values (:b, :o, :c, :a)"),
                      [{"b": batch_id, "o": job.org_id, "c": c, "a": a} for c, a in ledger.opening.items()])
        s.execute(text("insert into journal_entries(batch_id, org_id, entry_date, debit_account, credit_account, amount, reference) "
                       "values (:b, :o, :d, :dr, :cr, :a, :r)"),
                  [{"b": batch_id, "o": job.org_id, "d": e.date, "dr": e.debit_account, "cr": e.credit_account, "a": e.amount, "r": e.reference} for e in ledger.entries])
        s.execute(text("update import_jobs set status = 'COMPLETED', progress = 100, batch_id = :b, finished_at = now(), locked_until = null where id = :i"),
                  {"b": batch_id, "i": job.id})
        emit(s, SVC, "accounting.import.completed", job.org_id, f"batch/{batch_id}",
             {"org_id": job.org_id, "batch_id": batch_id, "period_start": ledger.period_start, "period_end": ledger.period_end, "content_hash": digest})
        record_audit(s, SVC, None, "import.completed", f"batch/{batch_id}", org_id=job.org_id)
    return "COMPLETED"


def run_one(db: Database, as_of: date | None = None) -> str | None:
    job = claim_next(db)
    return run_job(db, job, as_of) if job else None


class ImportWorker(threading.Thread):
    def __init__(self, db: Database, stop: threading.Event):
        super().__init__(daemon=True, name="import-worker")
        self.db, self.stop_event = db, stop

    def run(self):
        while not self.stop_event.is_set():
            try:
                if run_one(self.db) is None:
                    time.sleep(0.5)
            except Exception:
                log.exception("import worker iteration failed")
                time.sleep(2)
