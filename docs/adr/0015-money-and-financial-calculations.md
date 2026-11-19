# ADR-0015: Money and Financial Calculation Rules

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team (formula changes need approval by two people) |
| **Owner** | Financial Intelligence owner |
| **Related** | [ADR-0006](0006-api-contracts.md), [ADR-0013](0013-billing-and-sme-charging.md), [ADR-0025](0025-financial-data-pipeline.md) |

## Context

Data integrity is a driving characteristic. Assessments and fees are computed from accounting data. Floating-point errors, implicit rounding, or treating missing values as zero would produce wrong but plausible numbers, and in a distributed system the same value must mean the same thing in every service.

## Decision

1. **`Decimal` only** for money and ratios in every service; `float` is forbidden. A `Money(amount, currency)` type lives in the shared technical library ([ADR-0030](0030-repository-and-shared-libraries.md)).
2. **Currency:** CHF only in the MVP. Ledgers in other currencies get a quality flag; nothing is silently converted.
3. **Storage:** amounts `NUMERIC(19,4)`; ratios `NUMERIC(18,8)`.
4. **Rounding only at boundaries**, with an explicit rounding mode. Invoiced CHF amounts are rounded to 0.05 (to be confirmed with the accountant). Quotes contain the final rounded amount, so the charge needs no recalculation.
5. **Unavailable ≠ 0:** a metric that cannot be computed is stored as `NULL` with status `UNAVAILABLE` and a reason; division by zero yields `UNAVAILABLE`.
6. **Versioning:** every metric stores formula, mapping and source-batch versions; every assessment stores snapshot and scorecard versions ([ADR-0025](0025-financial-data-pipeline.md)).
7. **Serialization:** decimals are **strings** in JSON, both in APIs and in events. The web app formats but never computes financial values.
8. **Accounting invariants** are validated before a batch is accepted: debits = credits; assets = liabilities + equity after closing entries; consistent periods; no duplicates; plausibility checks.
9. Formulas, thresholds and scorecard weights are documented in `docs/financial-methodology.md`.

## Alternatives considered

| Option | Why not |
|---|---|
| Floats with rounding at the end | Binary errors; not reproducible |
| Integer cents | Fine for amounts, awkward for ratios and percentage fees |
| Missing = 0 | Turns "unknown" into "weak": an integrity and fairness defect |

## Consequences

**Positive**: exact, reproducible values that mean the same in every service.
**Negative**: a decimal-string formatter in the web app; careful coding.

## Compliance

FF-I1 (formula tests), FF-I2 (reproducibility), FF-I8 (no float in domain code), contract tests asserting decimal strings in APIs and event schemas.

## Revisit when

Multi-currency SMEs appear; or the pilot accountant defines different rounding or tax rules.
