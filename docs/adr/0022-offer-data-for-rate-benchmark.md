# ADR-0022: Retain Offer Data for the Rate Benchmark (the Data Moat)

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0011](0011-consistency-model.md), [ADR-0015](0015-money-and-financial-calculations.md), [ADR-0021](0021-matching-neutrality.md), [ADR-0031](0031-data-lifecycle-and-deletion.md) |

## Context

- Brainstorming: "Every offer on the platform sharpens our benchmark … **This is our moat, not the AI.**"
- The Fair Rate Benchmark is **illustrative** (V1) until real offers exist, then **empirical** (V2).
- If offers are deleted, mutable, or not linked to the risk context, the moat never accumulates.

## Decision

1. **LoanOffers are immutable and retained** after the application closes, linked to: application characteristics (amount, term, purpose, collateral), the **PublishedProfile** (assessment category, Data Confidence band, industry), and the outcome (selected / rejected / expired / withdrawn).
2. The **benchmark read model** lives in Marketplace (materialized views by risk category, amount band, term band and industry). No separate analytics store yet.
3. **Anonymization:** outputs only for groups with **≥ 5 offers from ≥ 3 lenders**; no lender- or SME-identifying data in outputs.
4. Every `RateEstimate` states version, assumptions, sources and limitations; V1 is labelled illustrative.
5. **On organization deletion**, offers are **anonymized** (organization references removed), not deleted, subject to legal review ([ADR-0031](0031-data-lifecycle-and-deletion.md)).
6. **Legal/business TODO:** lender terms must permit aggregated, anonymized use; SMEs are informed in the privacy notice.

## Alternatives considered

| Option | Why not |
|---|---|
| Delete offers after closure | Destroys the strategic asset |
| Separate analytics store now | Too little data; another copy of C3 data |
| Show benchmarks from few offers | Re-identification risk; statistically meaningless |

## Consequences

**Positive**: the moat accumulates from the first real offer; honest benchmark claims.
**Negative**: retention must be covered by agreements; the threshold hides the benchmark early on.

## Compliance

Tests: no output below thresholds; offers cannot be updated or deleted via any API; outputs contain no identifiers.

## Revisit when

Offer volume justifies a dedicated analytics service fed by events; or legal review sets retention limits.
