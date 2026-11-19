"""Pipeline stage: metrics -> assessment + Data Confidence (ADR-0025). Transparent rules, no ML (Master Plan §4).

The score is a PRELIMINARY, ILLUSTRATIVE rating. It is not a bank rating and not a probability of default. Insufficient
information lowers *Data Confidence*; it is not treated as weak performance (except where the rule says so explicitly).
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from credsort_common.money import D

from .metrics import CATALOGUE

SCORECARD_VERSION = "sc-1.0.0"
CONFIDENCE_VERSION = "conf-1.0.0"

# indicator -> (bad anchor, good anchor, weight). Points = clamp((value-bad)/(good-bad), 0, 1) * 100 (works for lower-is-better too).
INDICATORS = {
    "ebitda_margin": (Decimal("0.00"), Decimal("0.15"), 20),
    "net_profit_margin": (Decimal("0.00"), Decimal("0.08"), 10),
    "revenue_growth": (Decimal("-0.10"), Decimal("0.10"), 10),
    "current_ratio": (Decimal("0.80"), Decimal("1.50"), 15),
    "equity_ratio": (Decimal("0.10"), Decimal("0.40"), 20),
    "debt_to_ebitda": (Decimal("6.00"), Decimal("2.00"), 15),
    "dscr": (Decimal("1.00"), Decimal("2.00"), 10),
}
# unavailable because of weak performance (not missing data) scores worst
WORST_ON_REASONS = {"EBITDA_NOT_POSITIVE"}
CATEGORIES = [(75, "A", "Strong"), (55, "B", "Solid"), (35, "C", "Watch")]  # else D / Weak


def definition() -> dict:
    return {"indicators": {k: {"bad": str(b), "good": str(g), "weight": w} for k, (b, g, w) in INDICATORS.items()},
            "worst_on_reasons": sorted(WORST_ON_REASONS), "categories": [{"min": m, "category": c, "label": l} for m, c, l in CATEGORIES] + [{"min": 0, "category": "D", "label": "Weak"}]}


def category_for(score: int) -> tuple[str, str]:
    for minimum, cat, label in CATEGORIES:
        if score >= minimum:
            return cat, label
    return "D", "Weak"


def _points(value: Decimal, bad: Decimal, good: Decimal) -> Decimal:
    ratio = (value - bad) / (good - bad)
    return max(Decimal(0), min(Decimal(1), ratio)) * 100


def assess(metrics: list[dict]) -> dict:
    by_code = {m["code"]: m for m in metrics}
    factors, weighted, total_weight = [], Decimal(0), 0
    for code, (bad, good, weight) in INDICATORS.items():
        m = by_code.get(code)
        label = CATALOGUE[code][0]
        if m is None or (m["status"] != "OK" and m["reason"] not in WORST_ON_REASONS):
            factors.append({"code": code, "label": label, "value": None, "points": None, "weight": weight, "direction": "unknown",
                            "note": "Not enough data to rate this indicator"})
            continue
        pts = _points(D(m["value"]), bad, good) if m["status"] == "OK" else Decimal(0)
        weighted += pts * weight
        total_weight += weight
        direction = "positive" if pts >= 70 else "negative" if pts < 40 else "neutral"
        note = "EBITDA is not positive, so this indicator cannot be met" if m["status"] != "OK" else ""
        factors.append({"code": code, "label": label, "value": None if m["value"] is None else format(D(m["value"]), "f"),
                        "points": int(pts.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)), "weight": weight, "direction": direction, "note": note})
    if total_weight == 0:
        return {"score": None, "category": None, "label": None, "factors": factors}
    score = int((weighted / total_weight).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
    category, label = category_for(score)
    return {"score": score, "category": category, "label": label, "factors": factors}


def confidence(metrics: list[dict], snapshot: dict, as_of: date) -> dict:
    """Separate from the assessment: completeness, freshness, consistency, provenance (Master Plan §4.3)."""
    available = sum(1 for m in metrics if m["status"] == "OK" or m["reason"] in WORST_ON_REASONS)
    completeness = Decimal(available) / Decimal(len(CATALOGUE))
    period_end = date.fromisoformat(snapshot["period"]["end"])
    months = (as_of.year - period_end.year) * 12 + as_of.month - period_end.month
    freshness = Decimal(1) if months <= 13 else max(Decimal(0), 1 - Decimal(months - 13) / 24)
    q = snapshot["quality"]
    flags = len(q["unmapped_accounts"]) + (0 if abs(D(q["balance_gap"])) <= Decimal("0.01") else 1) + (0 if q["has_prior_year"] else 1)
    consistency = max(Decimal(0), 1 - Decimal("0.25") * flags)
    provenance = {"BEXIO": Decimal(1)}.get(q["source_type"], Decimal("0.4"))  # synthetic = demonstration data
    overall = Decimal("0.30") * completeness + Decimal("0.20") * freshness + Decimal("0.20") * consistency + Decimal("0.30") * provenance
    band = "HIGH" if overall >= Decimal("0.80") else "MEDIUM" if overall >= Decimal("0.60") else "LOW"
    f = lambda x: format(x.quantize(Decimal("0.001")), "f")
    return {"overall": f(overall), "band": band, "completeness": f(completeness), "freshness": f(freshness), "consistency": f(consistency),
            "provenance": f(provenance), "source_type": q["source_type"], "demo_data": q["source_type"] != "BEXIO"}
