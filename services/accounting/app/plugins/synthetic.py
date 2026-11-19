"""Synthetic accounting data: three internally consistent fictional SMEs with different risk profiles (ADR-0003, ADR-0024).

Deterministic: the same dataset and `as_of` always yield the byte-identical ledger. Double-entry by construction.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from ..domain.ledger import CanonicalLedger, Entry
from .base import ProviderError

CENT = Decimal("0.01")

CHART = {
    "1020": "Bank", "1100": "Trade receivables", "1200": "Inventory", "1500": "Machinery and equipment",
    "2000": "Trade payables", "2100": "Short-term bank debt", "2200": "Accrued expenses and VAT", "2450": "Long-term bank loan",
    "2800": "Share capital", "2970": "Retained earnings",
    "3000": "Revenue", "4000": "Cost of goods and services", "5000": "Personnel expenses",
    "6000": "Other operating expenses", "6800": "Depreciation", "6900": "Financial expenses", "8900": "Income taxes",
}

# Seasonality factors per month (sum = 12), deterministic.
SEASON = [0.85, 0.88, 0.97, 1.0, 1.05, 1.08, 1.0, 0.92, 1.05, 1.1, 1.08, 1.02]

PROFILES = {
    # healthy, moderately levered manufacturer
    "muster": dict(label="Muster Maschinenbau AG", revenue=2_400_000, growth=0.08, cogs=0.42, personnel=0.31, opex=0.15, fixed=1_100_000, dep_rate=0.12,
                   inventory=300_000, lt_debt=870_000, st_debt=0, rate=0.028, share_capital=300_000, cash=120_000, other_cl=0.09,
                   dividend=0.055, tax=0.13, capex=0.10),
    # struggling restaurant group
    "alpina": dict(label="Alpina Gastro GmbH", revenue=1_100_000, growth=-0.03, cogs=0.33, personnel=0.43, opex=0.20, fixed=450_000, dep_rate=0.12,
                   inventory=28_000, lt_debt=520_000, st_debt=60_000, rate=0.032, share_capital=20_000, cash=25_000, other_cl=0.04,
                   dividend=0.0, tax=0.13, capex=0.0),
    # fast-growing but thinly capitalised software studio
    "pixelwerk": dict(label="Pixelwerk Studio GmbH", revenue=720_000, growth=0.22, cogs=0.10, personnel=0.63, opex=0.20, fixed=60_000, dep_rate=0.25,
                      inventory=0, lt_debt=70_000, st_debt=0, rate=0.03, share_capital=40_000, cash=60_000, other_cl=0.10,
                      dividend=0.04, tax=0.13, capex=0.15),
}


def _c(x) -> Decimal:
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_EVEN)


def build_ledger(dataset: str, as_of: date) -> CanonicalLedger:
    if dataset not in PROFILES:
        raise ProviderError("UNKNOWN_DATASET", f"unknown synthetic dataset {dataset!r}; choose one of {sorted(PROFILES)}")
    p = PROFILES[dataset]
    y2 = as_of.year - 1
    y1 = y2 - 1
    start, end = date(y1, 1, 1), date(y2, 12, 31)
    rev_year = {y1: Decimal(str(p["revenue"])), y2: Decimal(str(p["revenue"])) * (1 + Decimal(str(p["growth"])))}

    cash, recv = _c(p["cash"]), _c(rev_year[y1] / 12 * Decimal("1.0"))
    inventory, fixed = _c(p["inventory"]), _c(p["fixed"])
    payables = _c(rev_year[y1] / 12 * Decimal(str(p["cogs"])))
    other_cl = _c(rev_year[y1] * Decimal(str(p["other_cl"])))  # accruals, VAT and prepayments: held constant
    st_debt, lt_debt = _c(p["st_debt"]), _c(p["lt_debt"])
    capital = _c(p["share_capital"])
    assets = cash + recv + inventory + fixed
    retained = assets - payables - other_cl - st_debt - lt_debt - capital  # balancing item (negative = accumulated losses)
    opening = {"1020": cash, "1100": recv, "1200": inventory, "1500": fixed, "2000": -payables, "2100": -st_debt, "2200": -other_cl,
               "2450": -lt_debt, "2800": -capital, "2970": -retained}
    opening = {c: a for c, a in opening.items() if a != 0}

    entries: list[Entry] = []
    seq = 0

    def add(d: date, debit: str, credit: str, amount: Decimal, label: str):
        nonlocal seq
        if amount <= 0:
            return
        seq += 1
        entries.append(Entry(d, debit, credit, amount, f"{label}-{seq:04d}"))

    running_cash = cash
    prev_revenue, prev_cogs = recv, payables
    debt_lt = lt_debt
    for year in (y1, y2):
        acc = {"revenue": Decimal(0), "costs": Decimal(0)}
        for m in range(12):
            d = date(year, m + 1, 28)
            revenue = _c(rev_year[year] / 12 * Decimal(str(SEASON[m])))
            cogs = _c(revenue * Decimal(str(p["cogs"])))
            personnel = _c(revenue * Decimal(str(p["personnel"])))
            opex = _c(revenue * Decimal(str(p["opex"])))
            dep = _c(fixed * Decimal(str(p["dep_rate"])) / 12)
            interest = _c(debt_lt * Decimal(str(p["rate"])) / 12)
            add(d, "1100", "3000", revenue, "INV")
            add(d, "1020", "1100", prev_revenue, "RCPT")
            add(d, "4000", "2000", cogs, "BILL")
            add(d, "2000", "1020", prev_cogs, "PAY")
            add(d, "5000", "1020", personnel, "SAL")
            add(d, "6000", "1020", opex, "OPEX")
            add(d, "6800", "1500", dep, "DEP")
            add(d, "6900", "1020", interest, "INT")
            running_cash += prev_revenue - prev_cogs - personnel - opex - interest
            acc["revenue"] += revenue
            acc["costs"] += cogs + personnel + opex + dep + interest
            if m == 5 and p["capex"]:  # yearly investment in June
                capex = _c(Decimal(str(p["fixed"])) * Decimal(str(p["capex"])))
                add(d, "1500", "1020", capex, "CAPEX")
                running_cash -= capex
                fixed += capex
            if m == 3 and p["dividend"]:  # dividend in April
                payout = _c(rev_year[year] * Decimal(str(p["dividend"])))
                add(date(year, 4, 28), "2970", "1020", payout, "DIV")
                running_cash -= payout
            if m == 11:  # income tax on the year's profit (none when the year ended in a loss)
                taxable = acc["revenue"] - acc["costs"]
                tax = _c(taxable * Decimal(str(p["tax"]))) if taxable > 0 else Decimal(0)
                add(date(year, 12, 29), "8900", "1020", tax, "TAX")
                running_cash -= tax
            if m == 11 and debt_lt > 0:  # yearly amortization in December
                repay = _c(min(debt_lt, _c(p["lt_debt"]) / 10))
                add(date(year, 12, 30), "2450", "1020", repay, "LOAN")
                running_cash -= repay
                debt_lt -= repay
            if running_cash < 15_000:  # keep the account in credit by drawing on the credit line
                draw = _c(15_000 - running_cash)
                add(d, "1020", "2100", draw, "DRAW")
                running_cash += draw
            prev_revenue, prev_cogs = revenue, cogs
    return CanonicalLedger("SYNTHETIC", start, end, dict(CHART), opening, entries)


class SyntheticProvider:
    def fetch(self, connection: dict, as_of: date) -> CanonicalLedger:
        return build_ledger(connection.get("config", {}).get("dataset", "muster"), as_of)
