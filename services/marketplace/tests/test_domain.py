from decimal import Decimal

import pytest

from app.domain import cost, matching
from app.domain.fields import CATALOGUE, SUMMARY_DEFAULT, employees_band, split
from app.domain.lifecycle import APPLICATION, OFFER, can_move

FULL = {"requested_amount": "500000", "term_months": 60, "industry": "Manufacturing", "assessment_category": "B", "confidence_band": "MEDIUM",
        "equity_ratio": "0.35", "ebitda_margin": "0.18", "debt_to_ebitda": "2.5", "assessment_score": 62}


def test_summary_default_is_privacy_preserving():
    assert "company_name" not in SUMMARY_DEFAULT and "revenue" not in SUMMARY_DEFAULT and set(SUMMARY_DEFAULT) <= set(CATALOGUE)
    assert split(["term_months", "dscr", "industry"]) == (["dscr"], ["term_months", "industry"])
    with pytest.raises(ValueError):
        split(["ledger"])
    assert [employees_band(n) for n in (3, 10, 80, 400, None)] == ["<10", "10-49", "50-249", "250+", None]


def test_criteria_validation_rejects_unknown_fields_and_bad_ranges():
    ok = matching.validate_criteria({"industries": [" Manufacturing "], "amount_min": "100000", "min": {"equity_ratio": "0.2"}, "max": {"debt_to_ebitda": "4"}})
    assert ok["industries"] == ["manufacturing"] and ok["min"] == {"equity_ratio": "0.2"}
    for bad in ({"ledger": 1}, {"min": {"industry": "1"}}, {"min_assessment_category": "Z"}, {"amount_min": "9", "amount_max": "1"}, {"weights": {"nope": 1}}, {"weights": {"dscr": 99}}):
        with pytest.raises(matching.InvalidCriteria):
            matching.validate_criteria(bad)


def test_eligibility_filters_and_explains():
    crit = matching.validate_criteria({"industries": ["manufacturing"], "amount_max": "1000000", "min": {"equity_ratio": "0.3"}, "max": {"debt_to_ebitda": "3"}, "min_assessment_category": "B"})
    m = matching.evaluate(crit, FULL)
    assert m is not None and all(e["met"] for e in m.explanation) and {e["criterion"] for e in m.explanation} >= {"Industry", "Assessment category"}
    assert matching.evaluate({**crit, "max": {"debt_to_ebitda": "2"}}, FULL) is None
    assert matching.evaluate({**crit, "min_assessment_category": "A"}, FULL) is None
    assert matching.evaluate({**crit, "industries": ["retail"]}, FULL) is None


def test_a_field_the_sme_did_not_permit_excludes_the_application_instead_of_revealing_anything():
    crit = matching.validate_criteria({"min": {"equity_ratio": "0.1"}})
    hidden = {k: v for k, v in FULL.items() if k != "equity_ratio"}
    assert matching.evaluate(crit, hidden) is None                       # not permitted -> excluded
    assert matching.evaluate(crit, {**hidden, "equity_ratio": None}) is None  # unavailable value -> excluded
    # excluded-because-hidden and excluded-because-failing are indistinguishable to the lender: no information about the value
    assert matching.evaluate(matching.validate_criteria({"min": {"equity_ratio": "0.9"}}), FULL) is None


def test_ranking_is_deterministic_and_uses_only_profile_and_criteria():
    crit = matching.validate_criteria({"weights": {"equity_ratio": 5, "ebitda_margin": 5}})
    strong, weak = {**FULL, "equity_ratio": "0.5", "ebitda_margin": "0.25"}, {**FULL, "equity_ratio": "0.15", "ebitda_margin": "0.02"}
    ms, mw = matching.evaluate(crit, strong), matching.evaluate(crit, weak)
    assert ms.score > mw.score and ms.score == Decimal("100.00")
    ranked = matching.rank([("b", "2026-01-02", mw), ("a", "2026-01-01", ms), ("c", "2026-01-01", ms)])
    assert [a for a, _ in ranked] == ["a", "c", "b"]   # score desc, then earlier publication, then id
    assert matching.rank([("b", "2026-01-02", mw), ("a", "2026-01-01", ms), ("c", "2026-01-01", ms)]) == ranked


def test_neutrality_matching_signature_has_no_commercial_inputs():
    import ast
    import inspect
    assert list(inspect.signature(matching.evaluate).parameters) == ["criteria", "fields"]
    tree = ast.parse(inspect.getsource(matching))
    imported = {a.name.lower() for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {(n.module or "").lower() for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name.lower() for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert not [m for m in imported if any(bad in m for bad in ("billing", "quote", "fee", "price", "plan"))]  # no commercial data can reach matching


def test_total_cost_methods():
    amount = Decimal("100000")
    bullet = cost.interest(amount, Decimal("3"), 60, "BULLET")
    linear = cost.interest(amount, Decimal("3"), 60, "LINEAR")
    annuity = cost.interest(amount, Decimal("3"), 60, "ANNUITY")
    assert bullet == Decimal("15000") and linear < bullet and annuity < bullet and annuity > linear
    assert cost.interest(amount, Decimal("0"), 60, "ANNUITY") == 0
    t = cost.total_cost(amount, Decimal("3"), 60, "BULLET", Decimal("500"), Decimal("1000"))
    assert t["total"] == t["interest"] + t["lender_fees"] + t["credsort_fee"] == Decimal("16500.0000")


def test_state_machines():
    assert can_move(APPLICATION, "OFFER_SELECTED", "FUNDED") and can_move(APPLICATION, "OFFER_SELECTED", "CANCELLED")
    assert not can_move(APPLICATION, "PUBLISHED", "FUNDED") and not can_move(APPLICATION, "FUNDED", "CANCELLED")  # a funded loan cannot be undone here
    assert can_move(OFFER, "SELECTED", "FUNDED") and not can_move(OFFER, "FUNDED", "FUNDED") and not can_move(OFFER, "WITHDRAWN", "SELECTED")
