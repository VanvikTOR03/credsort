"""Offer comparison: illustrative total financing cost, Decimal only (Master Plan §6.7)."""
from __future__ import annotations

from decimal import Decimal, getcontext

from credsort_common.money import q_amount

getcontext().prec = 40


def interest(amount: Decimal, rate_pct: Decimal, term_months: int, repayment: str) -> Decimal:
    r_year = rate_pct / 100
    if r_year == 0:
        return Decimal(0)
    if repayment == "BULLET":  # principal repaid at the end
        return amount * r_year * term_months / 12
    n = term_months
    if repayment == "LINEAR":  # equal principal instalments
        return amount * r_year / 12 * (n + 1) / 2
    r_m = r_year / 12  # ANNUITY: constant instalment
    payment = amount * r_m / (1 - (1 + r_m) ** -n)
    return payment * n - amount


def total_cost(amount: Decimal, rate_pct: Decimal, term_months: int, repayment: str, lender_fees: Decimal, credsort_fee: Decimal) -> dict:
    i = interest(amount, rate_pct, term_months, repayment)
    return {"interest": q_amount(i), "lender_fees": q_amount(lender_fees), "credsort_fee": q_amount(credsort_fee),
            "total": q_amount(i + lender_fees + credsort_fee)}
