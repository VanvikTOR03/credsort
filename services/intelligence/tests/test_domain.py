"""Pure pipeline tests: no database."""
from datetime import date
from decimal import Decimal

import pytest

from fixtures import ledger

from credsort_common.errors import Unprocessable

from app.domain import scenario as scn
from app.domain import scorecard as sc
from app.domain.mapping import category_for
from app.domain.metrics import CATALOGUE, compute_metrics
from app.domain.snapshot import PipelineError, build_snapshot

AS_OF = date(2026, 11, 19)


def run(**kw):
    snap = build_snapshot(ledger(**kw))
    metrics = compute_metrics(snap)
    return snap, metrics, {m["code"]: m for m in metrics}


def test_mapping_ranges():
    assert category_for("1020") == "CASH" and category_for("2450") == "LONG_TERM_DEBT" and category_for("6800") == "DEPRECIATION"
    assert category_for("9999") is None and category_for("abc") is None


def test_snapshot_balances_and_periods():
    snap, _, _ = run()
    assert snap["period"]["start"] == "2025-01-01" and snap["period"]["prior_start"] == "2024-01-01"
    assert Decimal(snap["quality"]["balance_gap"]) == 0
    cur = {k: Decimal(v) for k, v in snap["current"].items()}
    assert cur["revenue"] == Decimal("1100000.00") and cur["ebitda"] == cur["revenue"] - cur["cogs"] - cur["personnel"] - cur["other_opex"]
    assert cur["total_assets"] == cur["payables"] + cur["short_term_debt"] + cur["long_term_debt"] + cur["equity"]


def test_metric_values():
    _, _, m = run()
    assert m["revenue_growth"]["value"] == Decimal("0.10000000")
    assert m["ebitda_margin"]["value"] == Decimal("0.30000000")  # 1 - .30 - .30 - .10
    assert m["receivables_aging"]["status"] == "UNAVAILABLE" and m["receivables_aging"]["reason"] == "NO_INVOICE_LEVEL_DATA"
    assert all(m[c]["unit"] == CATALOGUE[c][1] for c in CATALOGUE)


def test_missing_data_is_unavailable_never_zero():
    _, _, m = run(drop_prior_year=True)
    assert m["revenue_growth"]["value"] is None and m["revenue_growth"]["status"] == "UNAVAILABLE" and m["revenue_growth"]["reason"] == "NO_PRIOR_YEAR"
    _, _, m = run(debt=0)
    assert m["debt_to_ebitda"]["value"] == 0  # no debt really means zero
    assert m["dscr"]["status"] == "OK" or m["dscr"]["reason"] == "NO_DEBT_SERVICE"


def test_negative_ebitda_is_weak_performance_not_missing_data():
    _, metrics, m = run(cogs=Decimal("0.60"), personnel=Decimal("0.40"), opex=Decimal("0.20"))
    assert m["debt_to_ebitda"]["status"] == "UNAVAILABLE" and m["debt_to_ebitda"]["reason"] == "EBITDA_NOT_POSITIVE"
    result = sc.assess(metrics)
    factor = next(f for f in result["factors"] if f["code"] == "debt_to_ebitda")
    assert factor["points"] == 0 and factor["direction"] == "negative"  # scored worst, not skipped


def test_unavailable_indicators_are_excluded_and_weights_renormalised():
    _, metrics, _ = run()
    full = sc.assess(metrics)
    stripped = [dict(m, status="UNAVAILABLE", value=None, reason="MISSING_DATA") if m["code"] == "dscr" else m for m in metrics]
    partial = sc.assess(stripped)
    dscr = next(f for f in partial["factors"] if f["code"] == "dscr")
    assert dscr["points"] is None and dscr["direction"] == "unknown"
    assert partial["score"] is not None and abs(partial["score"] - full["score"]) < 15


def test_scorecard_categories_and_bounds():
    assert sc.category_for(80) == ("A", "Strong") and sc.category_for(55) == ("B", "Solid") and sc.category_for(35) == ("C", "Watch") and sc.category_for(10) == ("D", "Weak")
    _, metrics, _ = run()
    r = sc.assess(metrics)
    assert 0 <= r["score"] <= 100 and r["category"] in "ABCD"


def test_healthy_vs_strained_company_get_different_categories():
    _, healthy, _ = run()
    _, strained, _ = run(cogs=Decimal("0.45"), personnel=Decimal("0.38"), opex=Decimal("0.14"), debt=600_000, cash=10_000, growth=Decimal("-0.08"))
    a, b = sc.assess(healthy), sc.assess(strained)
    assert a["score"] > b["score"] + 25 and a["category"] < b["category"]


def test_assessment_is_reproducible():
    one = ledger()
    a = sc.assess(compute_metrics(build_snapshot(one)))
    b = sc.assess(compute_metrics(build_snapshot(one)))
    assert a == b


def test_data_confidence_is_separate_and_flags_demo_data():
    snap, metrics, _ = run()
    c = sc.confidence(metrics, snap, AS_OF)
    assert c["band"] == "MEDIUM" and c["demo_data"] is True and c["provenance"] == "0.400"  # synthetic data caps confidence
    snap2, metrics2, _ = run(source="BEXIO")
    assert sc.confidence(metrics2, snap2, AS_OF)["band"] == "HIGH"
    stale = sc.confidence(metrics2, snap2, date(2030, 1, 1))
    assert Decimal(stale["freshness"]) < 1 and stale["band"] != "HIGH"


def test_unbalanced_ledger_is_rejected():
    bad = ledger()
    bad["opening"][0]["amount"] = "999999"
    with pytest.raises(PipelineError) as e:
        build_snapshot(bad)
    assert e.value.code == "BALANCE_MISMATCH"


def test_unmapped_account_lowers_consistency_not_the_score():
    snap = build_snapshot(ledger(with_unmapped=True))
    assert snap["quality"]["unmapped_accounts"] == ["9999"]
    assert Decimal(sc.confidence(compute_metrics(snap), snap, AS_OF)["consistency"]) == Decimal("0.75")


# ---- what-if --------------------------------------------------------------------------------
def test_debt_repayment_from_cash_respects_accounting_relationships():
    snap, _, _ = run(debt=200_000)
    out = scn.run(snap, {"debt_repayment_from_cash": "100000"})
    before = {m["code"]: m["value"] for m in out["before"]["metrics"]}
    after = {m["code"]: m["value"] for m in out["after"]["metrics"]}
    assert after["debt_to_ebitda"] < before["debt_to_ebitda"] and after["equity_ratio"] > before["equity_ratio"]  # less debt, smaller balance sheet
    assert after["current_ratio"] != before["current_ratio"] and "interest savings are not modelled" in " ".join(out["assumptions"])
    cur_after, _ = scn.apply_scenario(snap, {"debt_repayment_from_cash": "100000"})
    c = {k: Decimal(v) for k, v in cur_after["current"].items()}
    assert c["total_assets"] == c["payables"] + c["short_term_debt"] + c["long_term_debt"] + c["equity"]  # still balances


def test_scenario_cannot_create_cash_or_debt_out_of_thin_air():
    snap, _, _ = run(debt=200_000)
    snap["current"]["cash"] = "50000.00"  # little cash on hand at the end of the year
    with pytest.raises(Unprocessable) as e:
        scn.run(snap, {"debt_repayment_from_cash": "100000"})
    assert e.value.code == "repayment_exceeds_cash"
    with pytest.raises(Unprocessable) as e:
        scn.run(snap, {"debt_repayment_from_cash": "900000"})
    assert e.value.code == "repayment_exceeds_debt"
    with pytest.raises(Unprocessable):
        scn.run(snap, {"cost_reduction_pct": "80"})


def test_cost_reduction_and_revenue_scenarios_move_profit_into_equity():
    import copy
    snap, _, _ = run()
    baseline = copy.deepcopy(snap)
    after, _ = scn.apply_scenario(snap, {"cost_reduction_pct": "10"})
    assert snap == baseline  # the baseline snapshot is never modified
    b, a = ({k: Decimal(v) for k, v in s["current"].items()} for s in (snap, after))
    assert a["ebitda"] > b["ebitda"] and a["equity"] - b["equity"] == a["net_profit"] - b["net_profit"] and a["total_assets"] - b["total_assets"] == a["cash"] - b["cash"]
