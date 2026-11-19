"""State machines (docs/architecture 03, ADR-0011). The database constraints are the second layer."""
from __future__ import annotations

import datetime as dt

DISPUTE_WINDOW = dt.timedelta(days=14)

APPLICATION = {
    "DRAFT": {"PUBLISHED", "WITHDRAWN"},
    "PUBLISHED": {"OFFER_SELECTED", "WITHDRAWN"},
    "OFFER_SELECTED": {"FUNDED", "CANCELLED"},   # the lender confirms the payout, or the loan falls through
    "FUNDED": set(), "CANCELLED": set(), "WITHDRAWN": set(),
}
OFFER = {
    "SUBMITTED": {"SELECTED", "REJECTED", "WITHDRAWN", "EXPIRED"},
    "SELECTED": {"FUNDED", "CANCELLED"},
    "FUNDED": set(), "CANCELLED": set(), "REJECTED": set(), "WITHDRAWN": set(), "EXPIRED": set(),
}


def can_move(machine: dict, current: str, target: str) -> bool:
    return target in machine.get(current, set())
