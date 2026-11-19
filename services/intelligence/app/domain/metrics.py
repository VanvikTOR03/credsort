"""Pipeline stage: snapshot -> financial metrics (ADR-0025, ADR-0015). Unavailable is never zero."""
from __future__ import annotations

from decimal import Decimal

from credsort_common.money import D, q_ratio

FORMULA_VERSION = "f1"
Z = Decimal(0)

# code -> (label, unit)
CATALOGUE = {
    "revenue": ("Revenue", "CHF"),
    "revenue_growth": ("Revenue growth", "RATIO"),
    "ebitda_margin": ("EBITDA margin", "RATIO"),
    "net_profit_margin": ("Net profit margin", "RATIO"),
    "current_ratio": ("Current ratio", "RATIO"),
    "working_capital": ("Working capital", "CHF"),
    "equity_ratio": ("Equity ratio", "RATIO"),
    "debt_to_ebitda": ("Debt / EBITDA", "RATIO"),
    "dscr": ("Debt service coverage", "RATIO"),
    "receivables_aging": ("Receivables aging", "RATIO"),
}


def _ok(code: str, value: Decimal) -> dict:
    return {"code": code, "value": q_ratio(value), "unit": CATALOGUE[code][1], "status": "OK", "reason": None, "formula_version": FORMULA_VERSION}


def _na(code: str, reason: str) -> dict:
    return {"code": code, "value": None, "unit": CATALOGUE[code][1], "status": "UNAVAILABLE", "reason": reason, "formula_version": FORMULA_VERSION}


def compute_metrics(snapshot: dict) -> list[dict]:
    c = {k: D(v) for k, v in snapshot["current"].items()}
    prior = {k: D(v) for k, v in snapshot["prior"].items()} if snapshot.get("prior") else None
    out: list[dict] = [_ok("revenue", c["revenue"])]
    out.append(_ok("revenue_growth", c["revenue"] / prior["revenue"] - 1) if prior and prior["revenue"] > 0
               else _na("revenue_growth", "NO_PRIOR_YEAR" if not prior else "MISSING_DATA"))
    out.append(_ok("ebitda_margin", c["ebitda"] / c["revenue"]) if c["revenue"] > 0 else _na("ebitda_margin", "NO_REVENUE"))
    out.append(_ok("net_profit_margin", c["net_profit"] / c["revenue"]) if c["revenue"] > 0 else _na("net_profit_margin", "NO_REVENUE"))
    current_assets = c["cash"] + c["receivables"] + c["inventory"] + c["other_current_assets"]
    current_liabilities = c["payables"] + c["short_term_debt"] + c["other_current_liabilities"]
    out.append(_ok("current_ratio", current_assets / current_liabilities) if current_liabilities > 0 else _na("current_ratio", "NO_CURRENT_LIABILITIES"))
    out.append(_ok("working_capital", current_assets - current_liabilities))
    out.append(_ok("equity_ratio", c["equity"] / c["total_assets"]) if c["total_assets"] > 0 else _na("equity_ratio", "NO_ASSETS"))
    debt = c["short_term_debt"] + c["long_term_debt"]
    if debt == 0:
        out.append(_ok("debt_to_ebitda", Z))
    elif c["ebitda"] <= 0:
        out.append(_na("debt_to_ebitda", "EBITDA_NOT_POSITIVE"))  # weak performance, not missing data: the scorecard scores it as worst
    else:
        out.append(_ok("debt_to_ebitda", debt / c["ebitda"]))
    service = c["financial_expense"] + c["principal_repaid"]
    if service <= 0:
        out.append(_na("dscr", "NO_DEBT_SERVICE"))
    elif c["ebitda"] <= 0:
        out.append(_na("dscr", "EBITDA_NOT_POSITIVE"))
    else:
        out.append(_ok("dscr", c["ebitda"] / service))
    out.append(_na("receivables_aging", "NO_INVOICE_LEVEL_DATA"))  # needs invoice dates and payment status, which a ledger alone does not provide
    return out
