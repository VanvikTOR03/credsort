# ADR-0026: Freeze Permitted Fields as a Published Profile at Publication

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0008](0008-consent-and-permitted-field-matching.md), [ADR-0011](0011-consistency-model.md), [ADR-0021](0021-matching-neutrality.md), [ADR-0022](0022-offer-data-for-rate-benchmark.md) |

## Context

Marketplace needs some financial fields of an SME to run matching, but Intelligence owns them. Options are calling Intelligence on every matching query, replicating all metrics into Marketplace, or copying only what the SME consented to. Lenders must also see exactly what the SME previewed.

## Decision

1. At publication, Marketplace fetches from Intelligence (`profile-extract`) **only the permitted fields** of the **specific assessment ID** the SME previewed, and stores them as an immutable **PublishedProfile** in the same transaction as the publication and the DataDisclosure.
2. Matching, ranking, lender views and the benchmark use **only** PublishedProfiles. Marketplace never stores or queries non-permitted metrics or ledger data.
3. A newer assessment does **not** change a PublishedProfile. The SME sees "a newer assessment is available" and may **re-publish**, which creates a new PublishedProfile version and re-confirms consent (and a new quote if a fee applies).
4. For **full access**, the additional fields approved for one lender are frozen as a lender-specific profile at approval time.
5. Each PublishedProfile shows lenders its **as-of date** and assessment version.
6. On revocation, access to the profile is closed in the same transaction; on organization deletion, profiles follow [ADR-0031](0031-data-lifecycle-and-deletion.md).

## Alternatives considered

| Option | Why not |
|---|---|
| Call Intelligence on every matching query | Couples Marketplace availability and latency to Intelligence; every query becomes a cross-service call |
| Replicate all metrics into Marketplace | Copies non-consented confidential data; violates data minimization |
| Live view of the latest assessment | Lenders could see data the SME never previewed or approved |

## Consequences

**Positive**: data minimization; lenders see exactly what was consented; matching is independent of Intelligence's availability; integrity of "what was disclosed when".
**Negative**: profiles can be older than the latest assessment (by design, visible as-of date); re-publication is needed for updates.

## Compliance

- Test: a PublishedProfile contains exactly the permitted fields of the referenced assessment.
- Test: publication fails if the extract's assessment ID differs from the previewed one.
- Schema check: Marketplace's database has no columns for non-permitted metric types.

## Revisit when

SMEs want automatic refresh (consider an opt-in "auto-republish on new assessment" that re-confirms consent explicitly).
