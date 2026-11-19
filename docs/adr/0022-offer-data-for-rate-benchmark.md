# ADR-0022: Retain Offer Data for the Rate Benchmark (the Data Moat)

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0011](0011-transaction-boundaries-and-offer-concurrency.md), [ADR-0015](0015-money-and-financial-calculations.md), [ADR-0021](0021-matching-neutrality.md) |

## Context

- Brainstorming: "Every offer on the platform sharpens our benchmark. Over time, CredSort builds proprietary Swiss SME loan pricing data that no single bank or broker has. **This is our moat, not the AI.**"
- The Fair Rate Benchmark starts as **illustrative** (V1) and becomes **empirical** (V2) only with real offer data (Master Plan Stage 5, Architecture Plan §4.5).
- If offers are deleted, mutable, or not linked to the risk context, the moat never accumulates.

## Decision

1. **LoanOffers are immutable and retained** after the application closes, with links to: the application's characteristics (amount, term, purpose, collateral), the **assessment version and category**, the Data Confidence band, the industry, and the outcome (selected / rejected / expired / withdrawn).
2. The **benchmark read model** (aggregates of rates by risk category, amount band, term band and industry) is computed inside `lending` as materialized views; there is no data warehouse in the MVP.
3. **Anonymization:** benchmark outputs are aggregates with a **minimum group size (k ≥ 5 offers from ≥ 3 lenders)**; below that, nothing is shown. No lender-identifying or SME-identifying data appear in benchmark outputs.
4. Every `RateEstimate` states **version, assumptions, sources and limitations**; V1 is labelled **illustrative**.
5. **Legal/business TODO:** lender terms of use must allow aggregated, anonymized use of offer data; SMEs are informed in the privacy notice.

## Alternatives considered

| Option | Why not |
|---|---|
| Delete offers after closure | Destroys the strategic asset. |
| A separate analytics store now | Too little data to justify; adds a pipeline. |
| Show the benchmark from few offers | Re-identification risk; statistically meaningless. |

## Consequences

**Positive**: the moat accumulates from the first real offer; benchmark claims stay honest.
**Negative**: retention must be covered by the privacy notice and agreements; the k-threshold hides the benchmark early on.

## Compliance

- Test: benchmark queries return nothing below the k/lender thresholds.
- Test: offers cannot be updated or deleted through any API.
- Review: benchmark outputs contain no identifiers.

## Revisit when

Offer volume justifies a dedicated analytics store; or the legal review sets retention limits.
