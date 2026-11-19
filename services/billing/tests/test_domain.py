from decimal import Decimal

from app.domain.fees import Rule, compute, quote_amount


def pct(percent, min_amount=None, cap_amount=None):
    return Rule("R", "SME", "LOAN_FUNDED", "PERCENT_OF_PRINCIPAL", percent=Decimal(percent),
                min_amount=None if min_amount is None else Decimal(min_amount), cap_amount=None if cap_amount is None else Decimal(cap_amount))


def test_percent_fee_with_minimum_and_cap():
    rule = pct("0.75", "2000", "7500")
    assert compute(rule, Decimal("100000")) == Decimal("2000")   # 750 -> raised to the minimum
    assert compute(rule, Decimal("500000")) == Decimal("3750")
    assert compute(rule, Decimal("5000000")) == Decimal("7500")  # 37 500 -> capped


def test_fixed_fee_and_rounding_to_five_rappen_once():
    assert compute(Rule("F", "SME", "LOAN_FUNDED", "FIXED", amount=Decimal("199.99")), Decimal("1")) == Decimal("200.00")
    assert compute(pct("0.333"), Decimal("123457")) == Decimal("411.10")  # 411.1118... rounded once to 0.05


def test_quote_sums_rules_without_float_error():
    rules = [pct("0.01"), Rule("F", "SME", "LOAN_FUNDED", "FIXED", amount=Decimal("0.10"))]
    assert quote_amount(rules, Decimal("1000")) == Decimal("0.20")
    assert quote_amount([], Decimal("1000")) == 0
