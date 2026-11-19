# ADR-0008: Consent and Permitted-Field Matching (No Indirect Disclosure)

| | |
|---|---|
| **Status** | Proposed — formalizes Architecture Plan v1 §6 |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0017](0017-tenant-isolation.md), [ADR-0021](0021-matching-neutrality.md), [ADR-0019](0019-organization-types-and-delegation.md) |

## Context

Confidentiality is the top driving characteristic. Lenders search applications using criteria. Even *appearing* in a filtered result ("revenue > CHF 5M") discloses information, so it is not enough to hide values on the detail page.

## Decision

1. **Connecting bexio is not consent.** Nothing is visible to lenders until the SME **publishes** an application.
2. Publication always creates a **DataDisclosure**: `application_id`, `recipient_scope` (all verified lenders / a specific lender), `level` (`summary` / `full`), `purpose` (`matching` / `application_review`), **`permitted_fields`** (allowlist) and `revoked_at`.
3. Lenders can match, filter, sort, rank and count **only** on published applications and **only** on that application's permitted fields. An application whose allowlist does not cover a lender's criterion is **excluded** from that lender's results, not "matched with unknown".
4. Lender criteria may reference only fields from the platform's **allowlistable field catalogue**.
5. **`full` access** requires a separate, lender-specific approval by the SME (screen S11).
6. **Revocation** stops new reads and matching immediately. The UI states that copies a lender already received cannot be recalled.
7. Server-side checks: `access.api.can_view(ctx, application, level)` and `access.api.can_filter(ctx, field, application)` are called in every lending query and detail view, not in the UI.
8. The SME sees a **"what lenders see" preview** before publishing; the default allowlist is the summary set (industry, amount band, term, assessment category, Data Confidence band).

## Alternatives considered

| Option | Why not |
|---|---|
| Hide values only in the UI | Filters and counts still leak information. |
| All-or-nothing publication | Poor privacy and conversion; SMEs need granular control. |
| Matching on all fields but showing only permitted ones | Ranking position itself leaks the hidden values. |

## Consequences

**Positive**: privacy by design; a trust argument for SMEs and fiduciaries.
**Negative**: lenders see fewer matches when SMEs are restrictive; more complex queries; consent UX must be clear.

## Compliance

- Indirect-disclosure test suite: a lender with criteria on a non-permitted field must receive the same results, counts and order as if the application did not exist.
- Tests for revocation, `full` access approval and denial.
- Every lending query function takes an access context; no unscoped query helpers (review rule + test).

## Revisit when

Lenders need richer search (consider banded values or SME-approved templates); or real data and a legal review add requirements such as consent expiry.
