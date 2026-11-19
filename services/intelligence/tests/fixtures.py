"""A small but complete ledger (two fiscal years) in the shape Accounting's claim-check API returns."""
from __future__ import annotations

import uuid
from decimal import Decimal

CHART = [("1020", "Bank"), ("1100", "Trade receivables"), ("1500", "Equipment"), ("2000", "Trade payables"), ("2450", "Long-term loan"),
         ("2800", "Share capital"), ("3000", "Revenue"), ("4000", "Cost of goods"), ("5000", "Personnel"), ("6000", "Other opex"),
         ("6800", "Depreciation"), ("6900", "Interest")]


def ledger(*, revenue=1_000_000, growth=Decimal("0.10"), cogs=Decimal("0.30"), personnel=Decimal("0.30"), opex=Decimal("0.10"), debt=200_000,
           cash=150_000, payables=50_000, source="SYNTHETIC", batch_id=None, org_id=None, drop_prior_year=False, with_unmapped=False):
    """Each year: revenue booked and paid within the year, so balances stay simple and the ledger balances by construction."""
    entries = []
    years = [2025] if drop_prior_year else [2024, 2025]
    rev = {2024: Decimal(revenue), 2025: Decimal(revenue) * (1 + growth)}
    n = 0
    for y in years:
        r = rev[y]
        for debit, credit, amount in [("1020", "3000", r), ("4000", "1020", r * cogs), ("5000", "1020", r * personnel), ("6000", "1020", r * opex),
                                      ("6800", "1500", Decimal("20000")), ("6900", "1020", Decimal(debt) * Decimal("0.03")),
                                      ("2450", "1020", Decimal(min(20_000, debt)))]:
            if amount <= 0:
                continue
            n += 1
            entries.append({"date": f"{y}-06-30", "debit_account": debit, "credit_account": credit, "amount": str(amount.quantize(Decimal("0.01"))), "reference": f"E{n}"})
    fixed, loan, pay = Decimal("300000"), Decimal(debt), Decimal(payables)
    capital = Decimal(cash) + fixed - loan - pay
    opening = [("1020", Decimal(cash)), ("1500", fixed), ("2000", -pay), ("2450", -loan), ("2800", -capital)]
    opening = [(c, a) for c, a in opening if a != 0]
    accounts = [{"code": c, "name": n_} for c, n_ in CHART]
    if with_unmapped:
        accounts.append({"code": "9999", "name": "Mystery"})
    return {"batch_id": str(batch_id or uuid.uuid4()), "org_id": str(org_id or uuid.uuid4()), "source_type": source, "period_start": f"{years[0]}-01-01",
            "period_end": "2025-12-31", "content_hash": uuid.uuid4().hex, "normalizer_version": "norm-1", "validator_version": "val-1",
            "accounts": accounts, "opening": [{"account_code": c, "amount": str(a)} for c, a in opening], "entries": entries}
