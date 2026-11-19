# ADR-0015: Money and Financial Calculation Rules

| | |
|---|---|
| **Status** | Proposed — extends Architecture Plan v1 §4.2–4.3 |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team (both developers must approve formula changes) |
| **Owner** | Developer A (financial logic) |
| **Related** | [ADR-0006](0006-http-json-api-and-openapi-contract.md), [ADR-0013](0013-billing-and-sme-charging.md), [ADR-0010](0010-import-recovery-and-idempotency.md) |

## Context

Data integrity is a driving characteristic. Assessments and fee charges are computed from accounting data. Floating-point errors, implicit rounding or treating missing values as zero would produce wrong but plausible numbers.

## Decision

1. **`Decimal` only** in domain code (`decimal.Decimal`); `float` is forbidden for money and ratios. A `Money(amount: Decimal, currency: str)` value object lives in `shared`.
2. **Currency:** CHF only in the MVP. Ledgers in other currencies are flagged with a quality issue, not silently converted.
3. **Storage:** amounts `NUMERIC(19,4)`; ratios `NUMERIC(18,8)`.
4. **Rounding only at boundaries:** calculations run at full precision. Display and invoice amounts are rounded once, at the boundary. Invoiced CHF amounts are rounded to 0.05 (to be confirmed with the accountant). The rounding mode is explicit in code, never implicit.
5. **Unavailable ≠ 0:** a metric that cannot be computed is stored with `value = NULL`, status `UNAVAILABLE` and a reason. The scorecard defines how unavailable inputs are treated; division by zero yields `UNAVAILABLE`, not an exception or 0.
6. **Versioning:** every metric stores `formula_version`, `mapping_version` and its `source_import_id`; every assessment stores `snapshot_id`, `scorecard_version` and `assessment_version`. Snapshots, assessments and charges are **immutable**.
7. **Serialization:** decimals are sent as **strings** in JSON. The frontend formats but **never computes** financial values.
8. **Accounting invariants** are validated before a snapshot is created: debits = credits; assets = liabilities + equity (after closing entries); consistent periods; no duplicates; plausibility checks.
9. **Methodology document:** formulas, thresholds and scorecard weights live in `docs/financial-methodology.md` and are reviewed by both developers.

## Alternatives considered

| Option | Why not |
|---|---|
| Floats with rounding at the end | Accumulated binary errors; not reproducible across platforms. |
| Integer cents | Workable for amounts, awkward for ratios and percent fees; Decimal covers both. |
| Missing = 0 | Turns "we don't know" into "the company is weak": an integrity and fairness defect. |

## Consequences

**Positive**: exact, reproducible values; clear separation of missing data from weak performance.
**Negative**: more careful coding; the frontend needs a decimal-string formatter.

## Compliance

- Lint rule or test that forbids `float` in `*/domain/*` modules handling money or ratios.
- Unit tests for every formula, including boundary values, zero denominators and unavailable inputs.
- Reproducibility test: same snapshot + versions → byte-identical results.
- Contract test: API money fields are strings.

## Revisit when

Multi-currency SMEs appear; or the pilot accountant defines different rounding or tax rules.
