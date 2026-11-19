"""Local audit records written in the business transaction and forwarded to the Audit service (ADR-0028)."""
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from .events import emit
from .reqctx import request_id
from .security import AccessContext


def record_audit(session: Session, service: str, ctx: AccessContext | None, action: str, resource: str,
                 org_id: uuid.UUID | str | None = None, actor_user_id: uuid.UUID | None = None) -> uuid.UUID:
    """`org_id` = the represented organization (stream owner). Never include financial values or personal details."""
    stream = org_id or (ctx.effective_org_id if ctx else None)
    if stream is None:
        raise ValueError("audit record needs an organization")
    audit_id = uuid.uuid4()
    actor = ctx.user_id if ctx else actor_user_id
    acting = ctx.org_id if ctx else None
    behalf = ctx.on_behalf_of if ctx else None
    session.execute(
        text("insert into audit_records(id, org_id, actor_user_id, acting_org_id, on_behalf_of_org_id, action, resource, request_id) "
             "values (:i, :o, :a, :ao, :b, :act, :res, :rid)"),
        {"i": audit_id, "o": stream, "a": actor, "ao": acting, "b": behalf, "act": action, "res": resource, "rid": request_id()})
    emit(session, service, f"{service}.audit.recorded", stream, f"audit/{audit_id}",
         {"audit_id": audit_id, "actor_user_id": actor, "acting_org_id": acting, "on_behalf_of_org_id": behalf,
          "action": action, "resource": resource})
    return audit_id
