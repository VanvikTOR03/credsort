"""Lender matching (ADR-0021): eligibility filtering, then deterministic, explainable ranking.

PURE: the inputs are the lender's own criteria and the application's frozen PublishedProfile fields. No billing, no fees, no plans
and no other commercial attribute can reach this module (import rule + property test). Fields an SME did not permit are simply
absent, and an application that lacks a field a criterion needs is EXCLUDED, so a lender learns nothing about hidden values.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .fields import CATALOGUE

CATEGORY_RANK = {"A": 4, "B": 3, "C": 2, "D": 1}
CONFIDENCE_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
RATIO_MIN_FIELDS = {"revenue", "revenue_growth", "ebitda_margin", "net_profit_margin", "current_ratio", "working_capital", "equity_ratio", "dscr", "assessment_score"}
RATIO_MAX_FIELDS = {"debt_to_ebitda"}
# normalisation anchors for ranking: (worst, best)
ANCHORS = {"ebitda_margin": ("0", "0.25"), "net_profit_margin": ("0", "0.15"), "revenue_growth": ("-0.1", "0.2"), "current_ratio": ("0.8", "2.0"),
           "equity_ratio": ("0.1", "0.5"), "debt_to_ebitda": ("6", "0"), "dscr": ("1", "3"), "assessment_score": ("0", "100"), "revenue": ("0", "10000000"),
           "working_capital": ("0", "2000000")}
DEFAULT_WEIGHTS = {"assessment_score": 5}


class InvalidCriteria(ValueError):
    pass


def validate_criteria(criteria: dict) -> dict:
    """Normalises and validates a lender's criteria. Every referenced field must be in the allowlistable catalogue."""
    allowed_keys = {"industries", "amount_min", "amount_max", "term_min", "term_max", "min_assessment_category", "min_confidence", "min", "max", "weights"}
    extra = set(criteria) - allowed_keys
    if extra:
        raise InvalidCriteria(f"unknown criteria: {sorted(extra)}")
    out: dict[str, Any] = {}
    if criteria.get("industries"):
        out["industries"] = sorted({str(i).strip().lower() for i in criteria["industries"] if str(i).strip()})
    for k in ("amount_min", "amount_max"):
        if criteria.get(k) not in (None, ""):
            out[k] = format(Decimal(str(criteria[k])), "f")
    for k in ("term_min", "term_max"):
        if criteria.get(k) not in (None, ""):
            out[k] = int(criteria[k])
    if criteria.get("min_assessment_category"):
        if criteria["min_assessment_category"] not in CATEGORY_RANK:
            raise InvalidCriteria("min_assessment_category must be A, B, C or D")
        out["min_assessment_category"] = criteria["min_assessment_category"]
    if criteria.get("min_confidence"):
        if criteria["min_confidence"] not in CONFIDENCE_RANK:
            raise InvalidCriteria("min_confidence must be LOW, MEDIUM or HIGH")
        out["min_confidence"] = criteria["min_confidence"]
    for key, allowed in (("min", RATIO_MIN_FIELDS), ("max", RATIO_MAX_FIELDS | RATIO_MIN_FIELDS)):
        if criteria.get(key):
            bad = set(criteria[key]) - allowed
            if bad:
                raise InvalidCriteria(f"{key} cannot use {sorted(bad)}")
            out[key] = {f: format(Decimal(str(v)), "f") for f, v in criteria[key].items()}
    if criteria.get("weights"):
        bad = set(criteria["weights"]) - set(CATALOGUE)
        if bad:
            raise InvalidCriteria(f"weights reference unknown fields: {sorted(bad)}")
        out["weights"] = {f: int(w) for f, w in criteria["weights"].items() if int(w) > 0}
        if any(w > 10 for w in out["weights"].values()):
            raise InvalidCriteria("weights must be between 0 and 10")
    for lo, hi in (("amount_min", "amount_max"), ("term_min", "term_max")):
        if lo in out and hi in out and Decimal(str(out[lo])) > Decimal(str(out[hi])):
            raise InvalidCriteria(f"{lo} is greater than {hi}")
    return out


def required_fields(criteria: dict) -> set[str]:
    """Fields an application must have permitted for these criteria to apply to it at all."""
    need: set[str] = set()
    if criteria.get("industries"):
        need.add("industry")
    if "amount_min" in criteria or "amount_max" in criteria:
        need.add("requested_amount")
    if "term_min" in criteria or "term_max" in criteria:
        need.add("term_months")
    if "min_assessment_category" in criteria:
        need.add("assessment_category")
    if "min_confidence" in criteria:
        need.add("confidence_band")
    need |= set(criteria.get("min", {})) | set(criteria.get("max", {}))
    return need


@dataclass(frozen=True)
class Match:
    score: Decimal
    explanation: list[dict]


def _num(v) -> Decimal:
    return Decimal(str(v))


def evaluate(criteria: dict, fields: dict[str, Any]) -> Match | None:
    """None = not eligible (including: a required field is not permitted or has no value)."""
    for f in required_fields(criteria):
        if fields.get(f) is None:
            return None
    explanation: list[dict] = []

    def check(label: str, ok: bool, actual) -> bool:
        explanation.append({"criterion": label, "met": ok, "actual": None if actual is None else str(actual)})
        return ok

    if criteria.get("industries") and not check("Industry", str(fields["industry"]).lower() in criteria["industries"], fields["industry"]):
        return None
    if "amount_min" in criteria and not check("Amount at least", _num(fields["requested_amount"]) >= _num(criteria["amount_min"]), fields["requested_amount"]):
        return None
    if "amount_max" in criteria and not check("Amount at most", _num(fields["requested_amount"]) <= _num(criteria["amount_max"]), fields["requested_amount"]):
        return None
    if "term_min" in criteria and not check("Term at least", _num(fields["term_months"]) >= criteria["term_min"], fields["term_months"]):
        return None
    if "term_max" in criteria and not check("Term at most", _num(fields["term_months"]) <= criteria["term_max"], fields["term_months"]):
        return None
    if "min_assessment_category" in criteria and not check("Assessment category", CATEGORY_RANK[fields["assessment_category"]] >= CATEGORY_RANK[criteria["min_assessment_category"]], fields["assessment_category"]):
        return None
    if "min_confidence" in criteria and not check("Data confidence", CONFIDENCE_RANK[fields["confidence_band"]] >= CONFIDENCE_RANK[criteria["min_confidence"]], fields["confidence_band"]):
        return None
    for f, bound in criteria.get("min", {}).items():
        if not check(f"{CATALOGUE[f]} at least", _num(fields[f]) >= _num(bound), fields[f]):
            return None
    for f, bound in criteria.get("max", {}).items():
        if not check(f"{CATALOGUE[f]} at most", _num(fields[f]) <= _num(bound), fields[f]):
            return None
    return Match(_score(criteria.get("weights") or DEFAULT_WEIGHTS, fields), explanation)


def _normalise(field: str, value) -> Decimal:
    if field == "assessment_category":
        return Decimal(CATEGORY_RANK[value] - 1) / 3
    if field == "confidence_band":
        return Decimal(CONFIDENCE_RANK[value] - 1) / 2
    if field not in ANCHORS or value is None:
        return Decimal(0)
    worst, best = _num(ANCHORS[field][0]), _num(ANCHORS[field][1])
    return max(Decimal(0), min(Decimal(1), (_num(value) - worst) / (best - worst)))


def _score(weights: dict[str, int], fields: dict[str, Any]) -> Decimal:
    total = sum(weights.values()) or 1
    got = sum(w * _normalise(f, fields.get(f)) for f, w in weights.items() if fields.get(f) is not None)
    return (Decimal(got) / Decimal(total) * 100).quantize(Decimal("0.01"))


def rank(matches: list[tuple[str, str, Match]]) -> list[tuple[str, Match]]:
    """matches: (application_id, published_at iso, match). Score desc, then earlier publication, then id: fully deterministic."""
    return [(a, m) for a, _, m in sorted(matches, key=lambda x: (-x[2].score, x[1], x[0]))]
