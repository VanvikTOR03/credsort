# ADR-0021: Matching Neutrality and Explainable Ranking

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0002](0002-six-domain-modules.md), [ADR-0008](0008-consent-and-permitted-field-matching.md), [ADR-0013](0013-billing-and-sme-charging.md) |

## Context

The Brainstorming USPs promise **full neutrality**: "every lender pays the same disclosed fee, no lender can buy a better position, and we never lend or take credit decisions." With SMEs now paying and fees configurable, there is a temptation to rank by commercial value. Lenders and SMEs will only trust CredSort if neutrality holds in the code.

## Decision

1. **Lender-side ranking** is a **pure, deterministic function** of (the lender's own `LenderPreference` version, the application's **permitted** fields). It uses nothing else.
2. **Matching has two steps:** eligibility filtering (hard criteria) → preference ranking (weights). Lender preferences **never change** the company's Financial Assessment.
3. Ties are broken deterministically (publication time, then ID).
4. Each match carries an **explanation** (criteria met, score components) shown on the lender's matches screen.
5. **No paid placement**: no fee, plan, or commercial attribute of the lender or SME is an input to matching. Fee rules apply equally per rule to all lenders of the same type.
6. **SME-side offer comparison** sorts by the SME's chosen key (default: total financing cost), **never** by CredSort's revenue from the offer.
7. CredSort's fees are disclosed to the SME in the comparison view.

## Alternatives considered

| Option | Why not |
|---|---|
| "Featured lender" or sponsored ranking | Contradicts the USP; destroys trust and the benchmark's credibility. |
| Opaque ML ranking | Not explainable; harder to prove neutrality. |

## Consequences

**Positive**: a provable USP; ranking is testable and reproducible.
**Negative**: closes off advertising-style revenue.

## Compliance

- import-linter `forbidden` contract: `credsort.lending.domain.matching` may not import `credsort.billing`.
- A property test: for fixed inputs, ranking is identical across runs; changing any billing data does not change the ranking.
- Code review checklist item for any change to matching inputs.

## Revisit when

Never for paid placement without a new, explicit business decision recorded as a superseding ADR.
