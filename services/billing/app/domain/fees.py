"""Fee calculation: pure, Decimal only, rounding once at the boundary (ADR-0013, ADR-0015)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from credsort_common.money import D, q_amount, round_invoice_chf

DEFAULT_ENTITLEMENTS = ["PROFILE", "APPLY", "ADVISOR", "WHAT_IF"]  # every feature is included; companies pay once per loan request to unlock offers
TRIGGERS = {"LOAN_FUNDED"}  # fees quoted per offer and charged when the payout is confirmed
UNLOCK_TRIGGER = "OFFERS_UNLOCKED"  # the company's one-off fee, paid up front


@dataclass(frozen=True)
class Rule:
    code: str
    payer: str
    trigger: str
    calculator: str
    amount: Decimal | None = None
    percent: Decimal | None = None
    min_amount: Decimal | None = None
    cap_amount: Decimal | None = None


def compute(rule: Rule, basis: Decimal) -> Decimal:
    if rule.calculator == "FIXED":
        fee = D(rule.amount)
    else:
        fee = D(basis) * D(rule.percent) / 100
        if rule.min_amount is not None:
            fee = max(fee, D(rule.min_amount))
        if rule.cap_amount is not None:
            fee = min(fee, D(rule.cap_amount))
    return q_amount(round_invoice_chf(fee))


def quote_amount(rules: list[Rule], basis: Decimal) -> Decimal:
    return sum((compute(r, basis) for r in rules), Decimal(0))
