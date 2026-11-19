"""The allowlistable field catalogue (ADR-0008): the only things an SME can consent to share and a lender can match on."""
from __future__ import annotations

from decimal import Decimal

# field -> (label, owner). Intelligence-owned values are fetched at publication; marketplace-owned values come from the application.
INTELLIGENCE_FIELDS = {
    "assessment_category": "Assessment category", "assessment_score": "Assessment score", "confidence_band": "Data confidence",
    "revenue_band": "Revenue band", "revenue": "Revenue", "revenue_growth": "Revenue growth", "ebitda_margin": "EBITDA margin",
    "net_profit_margin": "Net profit margin", "current_ratio": "Current ratio", "working_capital": "Working capital",
    "equity_ratio": "Equity ratio", "debt_to_ebitda": "Debt / EBITDA", "dscr": "Debt service coverage",
}
MARKETPLACE_FIELDS = {
    "requested_amount": "Requested amount", "term_months": "Term (months)", "industry": "Industry", "employees_band": "Company size",
    "purpose": "Purpose", "collateral": "Collateral", "company_name": "Company name",
}
CATALOGUE = {**MARKETPLACE_FIELDS, **INTELLIGENCE_FIELDS}
# Pre-selected on the publish screen: the minimum useful, privacy-preserving set. Company name is never a default.
SUMMARY_DEFAULT = ["requested_amount", "term_months", "industry", "assessment_category", "confidence_band", "revenue_band", "employees_band"]


def employees_band(n: int | None) -> str | None:
    if n is None:
        return None
    return "<10" if n < 10 else "10-49" if n < 50 else "50-249" if n < 250 else "250+"


def split(fields: list[str]) -> tuple[list[str], list[str]]:
    """(intelligence-owned, marketplace-owned) preserving order; raises on unknown names."""
    unknown = [f for f in fields if f not in CATALOGUE]
    if unknown:
        raise ValueError(f"unknown fields: {unknown}")
    return [f for f in fields if f in INTELLIGENCE_FIELDS], [f for f in fields if f in MARKETPLACE_FIELDS]
