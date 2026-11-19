"""Pipeline stage: map account codes to financial categories (versioned, ADR-0025). Pure."""
from __future__ import annotations

MAPPING_VERSION = "kmu-ch-1.0.0"

# Swiss KMU-style chart ranges (inclusive). A new mapping is a NEW version; old snapshots stay reproducible.
RULES = [
    (1000, 1099, "CASH"), (1100, 1199, "RECEIVABLES"), (1200, 1299, "INVENTORY"), (1300, 1499, "OTHER_CURRENT_ASSETS"),
    (1500, 1999, "FIXED_ASSETS"), (2000, 2099, "PAYABLES"), (2100, 2199, "SHORT_TERM_DEBT"), (2200, 2399, "OTHER_CURRENT_LIABILITIES"),
    (2400, 2799, "LONG_TERM_DEBT"), (2800, 2999, "EQUITY"), (3000, 3999, "REVENUE"), (4000, 4999, "COGS"), (5000, 5999, "PERSONNEL"),
    (6000, 6799, "OTHER_OPEX"), (6800, 6899, "DEPRECIATION"), (6900, 6949, "FINANCIAL_EXPENSE"), (6950, 6999, "FINANCIAL_INCOME"),
    (7000, 7999, "OTHER_INCOME"), (8000, 8999, "EXTRAORDINARY"),
]

ASSET = {"CASH", "RECEIVABLES", "INVENTORY", "OTHER_CURRENT_ASSETS", "FIXED_ASSETS"}
CURRENT_ASSET = {"CASH", "RECEIVABLES", "INVENTORY", "OTHER_CURRENT_ASSETS"}
LIABILITY = {"PAYABLES", "SHORT_TERM_DEBT", "OTHER_CURRENT_LIABILITIES", "LONG_TERM_DEBT"}
CURRENT_LIABILITY = {"PAYABLES", "SHORT_TERM_DEBT", "OTHER_CURRENT_LIABILITIES"}
INCOME = {"REVENUE", "FINANCIAL_INCOME", "OTHER_INCOME"}
EXPENSE = {"COGS", "PERSONNEL", "OTHER_OPEX", "DEPRECIATION", "FINANCIAL_EXPENSE", "EXTRAORDINARY"}


def category_for(code: str) -> str | None:
    try:
        n = int(code)
    except ValueError:
        return None
    for low, high, cat in RULES:
        if low <= n <= high:
            return cat
    return None


def definition() -> dict:
    return {"rules": [{"from": a, "to": b, "category": c} for a, b, c in RULES]}
