from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import text

from credsort_common.db import set_context
from credsort_common.lifecycle import finish_deletion
from credsort_common.security import AccessContext

from .chain import LABELS, record_hash

SVC = "audit"


def ingest(session, event: dict) -> None:
    """Append one record to the organization's chain. Idempotent per source audit id."""
    set_context(session, None, "SYSTEM")
    d, org = event["data"], event["credsortorgid"]
    if session.execute(text("select 1 from audit_log where source_audit_id = :a"), {"a": d["audit_id"]}).first():
        return
    session.execute(text("insert into audit_streams(org_id) values (:o) on conflict do nothing"), {"o": org})
    head = session.execute(text("select head_seq, head_hash from audit_streams where org_id = :o for update"), {"o": org}).first()  # serialises per stream
    seq, prev = head.head_seq + 1, head.head_hash
    source = event["source"].rsplit("/", 1)[-1]
    occurred = dt.datetime.fromisoformat(event["time"])
    digest = record_hash(prev, org, seq, source, d["audit_id"], d["action"], d["resource"], occurred.astimezone(dt.timezone.utc).isoformat())
    session.execute(text("insert into audit_log(id, org_id, seq, prev_hash, hash, source_service, source_audit_id, actor_user_id, acting_org_id, on_behalf_of_org_id, action, resource, occurred_at) "
                         "values (:i, :o, :s, :p, :h, :src, :a, :u, :ao, :b, :act, :res, :t)"),
                    {"i": uuid.uuid4(), "o": org, "s": seq, "p": prev, "h": digest, "src": source, "a": d["audit_id"], "u": d["actor_user_id"], "ao": d["acting_org_id"],
                     "b": d["on_behalf_of_org_id"], "act": d["action"], "res": d["resource"], "t": occurred})
    session.execute(text("update audit_streams set head_seq = :s, head_hash = :h where org_id = :o"), {"s": seq, "h": digest, "o": org})


def verify_chain(session, org_id) -> dict:
    prev, expected_seq, count = "", 1, 0
    for r in session.execute(text("select seq, prev_hash, hash, source_service, source_audit_id, action, resource, occurred_at from audit_log where org_id = :o order by seq"), {"o": org_id}):
        digest = record_hash(r.prev_hash, org_id, r.seq, r.source_service, r.source_audit_id, r.action, r.resource, r.occurred_at.astimezone(dt.timezone.utc).isoformat())
        if r.seq != expected_seq or r.prev_hash != prev or r.hash != digest:
            return {"verified": False, "records": count, "broken_at": r.seq}
        prev, expected_seq, count = r.hash, expected_seq + 1, count + 1
    head = session.execute(text("select head_seq, head_hash from audit_streams where org_id = :o"), {"o": org_id}).first()
    if head and (head.head_seq != count or head.head_hash != prev):
        return {"verified": False, "records": count, "broken_at": count + 1}
    return {"verified": True, "records": count, "broken_at": None}


def activity(db, ctx: AccessContext, limit: int, before: int | None) -> list[dict]:
    org = ctx.effective_org_id
    with db.session(org) as s:
        rows = s.execute(text("select id, seq, action, resource, source_service, occurred_at, acting_org_id, on_behalf_of_org_id from audit_log "
                              "where (cast(:b as bigint) is null or seq < cast(:b as bigint)) order by seq desc limit :l"), {"b": before, "l": limit}).all()
    out = []
    for r in rows:
        by = "delegate" if r.on_behalf_of_org_id else "you" if r.acting_org_id == org else "platform" if r.acting_org_id is None else "other"
        out.append({"id": r.id, "seq": r.seq, "occurred_at": r.occurred_at, "action": r.action, "label": LABELS.get(r.action, r.action.replace(".", " ").capitalize()),
                    "source": r.source_service, "by": by})
    return out


def delete_org_data(session, org_id) -> None:
    """Records are retained as the legal trail; personal references (who exactly acted) are pseudonymised (ADR-0031)."""
    set_context(session, None, "SYSTEM")
    session.execute(text("update audit_log set actor_user_id = null where org_id = :o or acting_org_id = :o"), {"o": org_id})
    finish_deletion(session, SVC, org_id, tombstone=False)  # no tombstone: later audit events (e.g. other services' deletion confirmations) must still be recorded
