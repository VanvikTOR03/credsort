"""Pipeline stage: ledger -> FinancialSnapshot (ADR-0025). Pure, deterministic, Decimal only."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from credsort_common.money import D, q_amount

from .mapping import ASSET, CURRENT_ASSET, CURRENT_LIABILITY, EXPENSE, INCOME, LIABILITY, category_for


class PipelineError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


def _years_back(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # Feb 29
        return d.replace(year=d.year - years, day=28)


def _s(x: Decimal) -> str:
    return format(q_amount(x), "f")


def build_snapshot(ledger: dict) -> dict:
    """`ledger` is the claim-check JSON from Accounting (amounts as strings)."""
    period_start, period_end = date.fromisoformat(str(ledger["period_start"])), date.fromisoformat(str(ledger["period_end"]))
    cur_start = _years_back(period_end, 1) + timedelta(days=1)
    prior_end = cur_start - timedelta(days=1)
    prior_start = _years_back(prior_end, 1) + timedelta(days=1)
    has_prior = period_start <= prior_start

    unmapped = sorted({a["code"] for a in ledger["accounts"] if category_for(a["code"]) is None})
    opening = {o["account_code"]: D(o["amount"]) for o in ledger["opening"]}
    activity = {"prior": defaultdict(Decimal), "current": defaultdict(Decimal)}
    for e in ledger["entries"]:
        d = date.fromisoformat(str(e["date"]))
        bucket = "current" if d >= cur_start else "prior"
        amt = D(e["amount"])
        activity[bucket][e["debit_account"]] += amt
        activity[bucket][e["credit_account"]] -= amt

    def pl(bucket: str) -> dict[str, Decimal]:
        out: dict[str, Decimal] = defaultdict(Decimal)
        for code, net in activity[bucket].items():
            cat = category_for(code)
            if cat in INCOME:
                out[cat] += -net
            elif cat in EXPENSE:
                out[cat] += net
        return out

    def summarize(p: dict[str, Decimal]) -> dict:
        ebitda = p["REVENUE"] + p["OTHER_INCOME"] - p["COGS"] - p["PERSONNEL"] - p["OTHER_OPEX"]
        net = ebitda - p["DEPRECIATION"] - p["FINANCIAL_EXPENSE"] + p["FINANCIAL_INCOME"] - p["EXTRAORDINARY"]
        return {"revenue": p["REVENUE"], "cogs": p["COGS"], "personnel": p["PERSONNEL"], "other_opex": p["OTHER_OPEX"],
                "other_income": p["OTHER_INCOME"], "depreciation": p["DEPRECIATION"], "financial_expense": p["FINANCIAL_EXPENSE"],
                "financial_income": p["FINANCIAL_INCOME"], "extraordinary": p["EXTRAORDINARY"], "ebitda": ebitda, "net_profit": net}

    p_cur, p_prior = summarize(pl("current")), summarize(pl("prior"))

    def balances(*buckets: str) -> dict[str, Decimal]:
        bal: dict[str, Decimal] = defaultdict(Decimal)
        for code, amt in opening.items():
            bal[code] += amt
        for b in buckets:
            for code, net in activity[b].items():
                bal[code] += net
        return bal

    end_bal = balances("prior", "current")
    by_cat: dict[str, Decimal] = defaultdict(Decimal)
    equity_accounts = Decimal(0)
    for code, amt in end_bal.items():
        cat = category_for(code)
        if cat in ASSET:
            by_cat[cat] += amt
        elif cat in LIABILITY:
            by_cat[cat] += -amt
        elif cat == "EQUITY":
            equity_accounts += -amt
    cumulative_profit = p_cur["net_profit"] + p_prior["net_profit"]
    equity = equity_accounts + cumulative_profit
    total_assets = sum((by_cat[c] for c in ASSET), Decimal(0))
    total_liabilities = sum((by_cat[c] for c in LIABILITY), Decimal(0))
    gap = total_assets - total_liabilities - equity

    # repayments of long-term debt in the current year (debits on those accounts), for the debt-service ratio
    principal_repaid = Decimal(0)
    for e in ledger["entries"]:
        if date.fromisoformat(str(e["date"])) >= cur_start and category_for(e["debit_account"]) == "LONG_TERM_DEBT":
            principal_repaid += D(e["amount"])

    quality = {"unmapped_accounts": unmapped, "balance_gap": _s(gap), "has_prior_year": has_prior,
               "source_type": ledger["source_type"], "content_hash": ledger["content_hash"]}
    if abs(gap) > Decimal("1.00"):
        raise PipelineError("BALANCE_MISMATCH", f"assets differ from liabilities + equity by {_s(gap)}")
    return {
        "period": {"start": cur_start.isoformat(), "end": period_end.isoformat(), "prior_start": prior_start.isoformat() if has_prior else None,
                   "prior_end": prior_end.isoformat() if has_prior else None},
        "current": {**{k: _s(v) for k, v in p_cur.items()},
                    "cash": _s(by_cat["CASH"]), "receivables": _s(by_cat["RECEIVABLES"]), "inventory": _s(by_cat["INVENTORY"]),
                    "other_current_assets": _s(by_cat["OTHER_CURRENT_ASSETS"]), "fixed_assets": _s(by_cat["FIXED_ASSETS"]),
                    "payables": _s(by_cat["PAYABLES"]), "short_term_debt": _s(by_cat["SHORT_TERM_DEBT"]),
                    "other_current_liabilities": _s(by_cat["OTHER_CURRENT_LIABILITIES"]), "long_term_debt": _s(by_cat["LONG_TERM_DEBT"]),
                    "equity": _s(equity), "total_assets": _s(total_assets), "principal_repaid": _s(principal_repaid)},
        "prior": {k: _s(v) for k, v in p_prior.items()} if has_prior else None,
        "quality": quality,
    }
