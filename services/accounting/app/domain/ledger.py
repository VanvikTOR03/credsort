"""Canonical ledger and validation: pure functions, no I/O (ADR-0025 stages 2-3). Amounts are Decimal; debit-positive."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

NORMALIZER_VERSION = "norm-1"
VALIDATOR_VERSION = "val-1"


@dataclass(frozen=True)
class Entry:
    date: date
    debit_account: str
    credit_account: str
    amount: Decimal
    reference: str


@dataclass
class CanonicalLedger:
    source_type: str
    period_start: date
    period_end: date
    accounts: dict[str, str]                 # code -> name
    opening: dict[str, Decimal]              # code -> signed amount (debit positive: assets +, liabilities/equity -)
    entries: list[Entry] = field(default_factory=list)


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    blocking: bool = True


def canonical_json(ledger: CanonicalLedger) -> str:
    return json.dumps({
        "period": [ledger.period_start.isoformat(), ledger.period_end.isoformat()],
        "accounts": sorted(ledger.accounts.items()),
        "opening": sorted((c, format(a, "f")) for c, a in ledger.opening.items()),
        "entries": sorted((e.date.isoformat(), e.reference, e.debit_account, e.credit_account, format(e.amount, "f")) for e in ledger.entries),
    }, sort_keys=True, separators=(",", ":"))


def content_hash(ledger: CanonicalLedger) -> str:
    return hashlib.sha256(canonical_json(ledger).encode()).hexdigest()


def validate(ledger: CanonicalLedger) -> list[Issue]:
    """Accounting invariants checked before a batch is accepted (ADR-0015 §8)."""
    issues: list[Issue] = []
    if ledger.period_end <= ledger.period_start:
        issues.append(Issue("INVALID_PERIOD", "period end must be after period start"))
    if not ledger.entries:
        issues.append(Issue("NO_ENTRIES", "the ledger contains no journal entries"))
    seen: set[str] = set()
    for e in ledger.entries:
        if e.debit_account not in ledger.accounts or e.credit_account not in ledger.accounts:
            issues.append(Issue("UNKNOWN_ACCOUNT", f"entry {e.reference} references an account that is not in the chart"))
        if e.amount <= 0:
            issues.append(Issue("NON_POSITIVE_AMOUNT", f"entry {e.reference} has a non-positive amount"))
        if not (ledger.period_start <= e.date <= ledger.period_end):
            issues.append(Issue("OUT_OF_PERIOD", f"entry {e.reference} is dated outside the period"))
        if e.debit_account == e.credit_account:
            issues.append(Issue("SAME_ACCOUNT", f"entry {e.reference} debits and credits the same account"))
        if e.reference in seen:
            issues.append(Issue("DUPLICATE_ENTRY", f"entry reference {e.reference} appears twice"))
        seen.add(e.reference)
    unknown_open = [c for c in ledger.opening if c not in ledger.accounts]
    if unknown_open:
        issues.append(Issue("UNKNOWN_ACCOUNT", "opening balances reference accounts that are not in the chart"))
    if sum(ledger.opening.values(), Decimal(0)) != 0:
        issues.append(Issue("OPENING_UNBALANCED", "opening balances do not satisfy assets = liabilities + equity"))
    return issues
