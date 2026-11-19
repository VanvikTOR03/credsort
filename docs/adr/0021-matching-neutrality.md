# ADR-0021: Matching Neutrality and Explainable Ranking

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0002](0002-service-decomposition.md), [ADR-0008](0008-consent-and-permitted-field-matching.md), [ADR-0013](0013-billing-and-sme-charging.md) |

## Context

The Brainstorming USPs promise **full neutrality**: "every lender pays the same disclosed fee, no lender can buy a better position." With SMEs now paying and fees configurable, neutrality must be guaranteed structurally, not just promised.

## Decision

1. **Lender-side ranking** is a **pure, deterministic function** of (the lender's own LenderPreference version, the application's PublishedProfile). Nothing else is an input.
2. **Two steps:** eligibility filtering (hard criteria) → preference ranking (weights). Lender preferences never change an assessment.
3. Ties break deterministically (publication time, then ID).
4. Each match carries an **explanation** (criteria met, score components).
5. **No paid placement.** Fees, plans, quotes or any commercial attribute of the lender or SME are not inputs. Structurally: pricing lives in a different service (Billing), and Marketplace's matching module cannot access the quote cache.
6. **SME-side comparison** sorts by the SME's chosen key (default: total financing cost), never by CredSort's revenue; CredSort's fee per offer is shown.

## Alternatives considered

| Option | Why not |
|---|---|
| Sponsored ranking | Contradicts the USP; destroys trust and benchmark credibility |
| Opaque ML ranking | Not explainable; neutrality not provable |

## Consequences

**Positive**: a provable USP; reproducible ranking.
**Negative**: advertising-style revenue is closed off.

## Compliance

- Import rule: Marketplace `matching` module may not import the `quotes` module.
- FF-F2 property test: identical inputs → identical ranking; changing any billing data never changes ranking.

## Revisit when

Only with an explicit business decision recorded in a superseding ADR.
