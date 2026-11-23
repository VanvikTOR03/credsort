"""Deterministic explanations and the "no invented numbers" guard (ADR-0009, FF-F4). Pure.

The AI layer only EXPLAINS numbers calculated by Financial Intelligence. It never calculates, changes or promises anything.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation

PERCENT = {"revenue_growth", "ebitda_margin", "net_profit_margin", "equity_ratio"}
CHF = {"revenue", "working_capital"}
LABEL = {"revenue": "Revenue", "revenue_growth": "Revenue growth", "ebitda_margin": "EBITDA margin", "net_profit_margin": "Net profit margin",
         "current_ratio": "Current ratio", "working_capital": "Working capital", "equity_ratio": "Equity ratio", "debt_to_ebitda": "Debt / EBITDA",
         "dscr": "Debt service coverage", "receivables_aging": "Receivables aging"}
ADVICE = {
    "ebitda_margin": "Raising prices, trimming cost of goods or reducing operating costs lifts the EBITDA margin.",
    "net_profit_margin": "Lower financing and depreciation costs, or higher operating profit, improve the net margin.",
    "revenue_growth": "Winning repeat customers and new markets supports growth; lenders look for a stable or rising trend.",
    "current_ratio": "Collecting receivables faster or reducing short-term obligations strengthens short-term liquidity.",
    "equity_ratio": "Retaining profits or adding equity raises the equity ratio, which lenders weigh heavily.",
    "debt_to_ebitda": "Repaying debt from free cash or growing EBITDA reduces leverage.",
    "dscr": "Higher operating profit or a longer repayment profile improves the ability to service debt.",
}
DISCLAIMER = "AI-generated explanation of a preliminary, illustrative assessment. It is not a bank rating, not a probability of default and not financial advice."


def fmt(code: str, value) -> str:
    if value is None:
        return "not available"
    v = Decimal(str(value))
    if code in CHF:
        return f"CHF {v:,.0f}".replace(",", "'")
    if code in PERCENT:
        return f"{v * 100:.1f}%"
    return f"{v:.2f}x"


def _metrics(ctx: dict) -> dict:
    return {m["code"]: m for m in ctx["metrics"]}


def explain_assessment(ctx: dict) -> dict:
    a, conf = ctx["assessment"], ctx["assessment"]["confidence"]
    strengths, concerns, unknown, suggestions = [], [], [], []
    for f in a["factors"]:
        code = f["code"]
        if f["direction"] == "positive":
            strengths.append(f"{LABEL[code]} of {fmt(code, f['value'])} supports the assessment.")
        elif f["direction"] == "negative":
            concerns.append(f"{LABEL[code]} of {fmt(code, f['value'])} weighs on the assessment." if f["value"] is not None
                            else f"{LABEL[code]} cannot be met because EBITDA is not positive.")
            if code in ADVICE:
                suggestions.append(ADVICE[code])
        elif f["direction"] == "unknown":
            unknown.append(f"{LABEL[code]} could not be rated: not enough data.")
    note = f"Data confidence is {conf['band'].lower()}" + (" and the figures come from demonstration data." if conf.get("demo_data") else ".")
    return {"headline": f"Category {a['category']} ({a['label']}), score {a['score']} out of 100",
            "summary": f"Based on figures up to {ctx['period_end']}, your preliminary assessment is category {a['category']} ({a['label']}) with a score of {a['score']} out of 100. {note}",
            "strengths": strengths, "concerns": concerns, "data_gaps": unknown, "suggestions": suggestions[:4]}


def explain_scenario(ctx: dict) -> dict:
    sc = ctx["scenario"]["result"]
    before, after = sc["before"]["assessment"], sc["after"]["assessment"]
    bm, am = {m["code"]: m for m in sc["before"]["metrics"]}, {m["code"]: m for m in sc["after"]["metrics"]}
    better, worse = [], []
    for code in LABEL:
        b, a = bm.get(code, {}).get("value"), am.get(code, {}).get("value")
        if b is None or a is None or Decimal(str(b)) == Decimal(str(a)):
            continue
        line = f"{LABEL[code]} moves from {fmt(code, b)} to {fmt(code, a)}."
        improves = (Decimal(str(a)) < Decimal(str(b))) if code == "debt_to_ebitda" else (Decimal(str(a)) > Decimal(str(b)))
        (better if improves else worse).append(line)
    head = (f"Score moves from {before['score']} to {after['score']}; category {before['category']} to {after['category']}"
            if before["score"] != after["score"] else f"Score stays at {after['score']}; category {after['category']}")
    return {"headline": head, "summary": "This what-if scenario was calculated deterministically on a copy of your figures. " + " ".join(sc["assumptions"]),
            "strengths": better, "concerns": worse, "data_gaps": [], "suggestions": []}


def coach_reply(question: str, ctx: dict) -> str:
    """Deterministic fallback for the assistant chat: built only from the verified explanation, never from free text."""
    e = explain_assessment(ctx)
    q = question.lower()
    if any(w in q for w in ("improve", "increase", "raise", "better", "higher", "upgrade", "boost", "fix")):
        if e["suggestions"]:
            return "Here is what would help most right now: " + " ".join(e["suggestions"][:3]) + " You can try the what-if tab to see the effect before changing anything."
        return "Nothing in your figures stands out as a weakness. Keeping profit stable and debt low is the best way to hold your category."
    if any(w in q for w in ("why", "reason", "weigh", "low", "bad")):
        return " ".join((e["concerns"] or e["strengths"])[:2]) or e["summary"]
    return e["summary"] + " Ask me how to improve your rating or what a figure means."


# ---- the guard ------------------------------------------------------------------------------
_NUM = re.compile(r"\d[\d',]*\.?\d*")


_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def numbers_in(text: str) -> list[Decimal]:
    """Numbers a reader could take for a metric. ISO dates are dates, not metrics (their year is checked via the context's dates)."""
    out = [Decimal(d[:4]) for d in _DATE.findall(text)]
    for m in _NUM.findall(_DATE.sub(" ", text)):
        try:
            out.append(Decimal(m.replace("'", "").replace(",", "").rstrip(".")))
        except InvalidOperation:
            pass
    return out


def allowed_numbers(ctx: dict) -> set[Decimal]:
    nums: set[Decimal] = {*map(Decimal, range(0, 11)), Decimal(100)}  # counts, ordinals ("three indicators") and the fixed 0-100 score scale
    def add(v):
        try:
            d = Decimal(str(v))
        except (InvalidOperation, TypeError):
            return
        for x in (d, d * 100, d.quantize(Decimal("0.1")), (d * 100).quantize(Decimal("0.1")), d.quantize(Decimal("0.01")), d.quantize(Decimal("1"))):
            nums.add(abs(x))
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("value", "score", "points", "overall", "completeness", "freshness", "consistency", "provenance", "weight"):
                    add(v)
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            for n in re.findall(r"\d{4}", o):  # years in dates
                nums.add(Decimal(n))
            if o.replace(".", "", 1).replace("-", "", 1).isdigit():
                add(o)
    walk(ctx)
    return nums


def invented_numbers(output: dict, ctx: dict, rounding: bool = False) -> list[Decimal]:
    """Numbers in `output` that cannot be traced to `ctx`. Free-form chat may round (31 for 31.16); explanations may not."""
    allowed = allowed_numbers(ctx)
    bad = []
    for n in numbers_in(json.dumps(output, ensure_ascii=False)):
        tol = Decimal("0.5") if rounding and n == n.to_integral_value() else Decimal("0.06")
        if not any(abs(abs(n) - a) <= tol for a in allowed):
            bad.append(n)
    return bad
