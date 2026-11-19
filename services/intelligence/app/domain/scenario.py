"""What-if scenarios: deterministic recalculation on a COPY of the snapshot (Master Plan §10.3). The AI only explains results.

Accounting relationships are respected: repaying debt from cash lowers cash and debt equally; profit changes raise equity and
cash by the same amount. Simplifications are listed in the result as assumptions.
"""
from __future__ import annotations

import copy
from decimal import Decimal

from credsort_common.errors import Unprocessable
from credsort_common.money import D, q_amount

from .metrics import compute_metrics
from .scorecard import assess


def apply_scenario(snapshot: dict, inputs: dict) -> tuple[dict, list[str]]:
    snap = copy.deepcopy(snapshot)
    c = {k: D(v) for k, v in snap["current"].items()}
    repay = D(inputs.get("debt_repayment_from_cash", 0))
    revenue_change = D(inputs.get("revenue_change_pct", 0)) / 100
    cost_cut = D(inputs.get("cost_reduction_pct", 0)) / 100
    assumptions: list[str] = []
    if repay < 0 or cost_cut < 0 or cost_cut > Decimal("0.5") or revenue_change < Decimal("-0.9") or revenue_change > 5:
        raise Unprocessable("scenario inputs are outside the supported range", code="scenario_out_of_range")
    debt = c["short_term_debt"] + c["long_term_debt"]
    if repay > debt:
        raise Unprocessable("repayment exceeds the outstanding debt", code="repayment_exceeds_debt")
    if repay > c["cash"]:
        raise Unprocessable("repayment exceeds available cash", code="repayment_exceeds_cash")
    if repay:
        from_short = min(repay, c["short_term_debt"])
        c["short_term_debt"] -= from_short
        c["long_term_debt"] -= repay - from_short
        c["cash"] -= repay
        c["total_assets"] -= repay
        assumptions.append("Debt is repaid from cash, shortest-term debt first; interest savings are not modelled.")
    delta_profit = Decimal(0)
    if revenue_change:
        d_rev = c["revenue"] * revenue_change
        d_cogs = c["cogs"] * revenue_change  # cost of goods and services varies with revenue
        c["revenue"] += d_rev
        c["cogs"] += d_cogs
        c["ebitda"] += d_rev - d_cogs
        delta_profit += d_rev - d_cogs
        assumptions.append("Cost of goods and services moves proportionally with revenue; personnel and other operating costs stay fixed.")
    if cost_cut:
        saving = (c["personnel"] + c["other_opex"]) * cost_cut
        c["personnel"] -= c["personnel"] * cost_cut
        c["other_opex"] -= c["other_opex"] * cost_cut
        c["ebitda"] += saving
        delta_profit += saving
        assumptions.append("Personnel and other operating costs are reduced by the given percentage.")
    if delta_profit:
        c["net_profit"] += delta_profit
        c["equity"] += delta_profit
        c["cash"] += delta_profit
        c["total_assets"] += delta_profit
        assumptions.append("Profit changes flow fully into cash and equity; taxes and working-capital effects are not modelled.")
    snap["current"] = {k: format(q_amount(v), "f") for k, v in c.items()}
    return snap, assumptions


def run(snapshot: dict, inputs: dict) -> dict:
    before_metrics = compute_metrics(snapshot)
    after_snapshot, assumptions = apply_scenario(snapshot, inputs)
    after_metrics = compute_metrics(after_snapshot)
    return {"before": {"metrics": before_metrics, "assessment": assess(before_metrics)},
            "after": {"metrics": after_metrics, "assessment": assess(after_metrics)}, "assumptions": assumptions}
