from __future__ import annotations

from credsort_common.config import env
from credsort_common.db import Database, set_context
from credsort_common.security import AccessContext


def sess(db: Database, ctx: AccessContext):
    """RLS session for a request: lenders see only consented data, SMEs (or their delegates) only their own."""
    role = "LENDER" if ctx.org_type == "LENDER" else "SME" if ctx.org_type in ("SME", "FIDUCIARY") else "NONE"
    return db.session(ctx.effective_org_id, role)


def as_system(session) -> None:
    """Narrow, explicit elevation inside a transaction (e.g. a lender confirming payout of ITS selected offer updates the SME-owned row)."""
    set_context(session, None, "SYSTEM")


def pilot_cap():
    from decimal import Decimal
    value = env("PILOT_MAX_AMOUNT")
    return Decimal(value) if value else None
