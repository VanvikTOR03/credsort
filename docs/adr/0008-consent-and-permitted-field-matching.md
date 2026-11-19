# ADR-0008: Consent Lives in Marketplace; Matching Uses Only Permitted Fields

| | |
|---|---|
| **Status** | Proposed — formalizes Architecture Plan v1 §6; consent ownership moved to Marketplace |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0002](0002-service-decomposition.md), [ADR-0017](0017-tenant-isolation.md), [ADR-0021](0021-matching-neutrality.md), [ADR-0026](0026-published-profile-snapshots.md) |

## Context

Confidentiality is the top characteristic. Even *appearing* in a filtered result ("revenue > CHF 5M") discloses information, so hiding values on the detail page is not enough. Consent must be checked on every matching query, and revocation must take effect immediately.

## Decision

1. **Connecting bexio is not consent.** Nothing is visible to lenders until the SME publishes an application.
2. **Consent (DataDisclosure) is owned by Marketplace**, in the same database as applications, published profiles and matching, so publication + consent is one transaction and revocation is effective immediately.
3. A DataDisclosure records `application_id`, `recipient_scope` (all verified lenders / one lender), `level` (`summary` / `full`), `purpose` (`matching` / `application_review`), **`permitted_fields`**, `revoked_at`.
4. Lenders can match, filter, sort, rank and count **only** on published applications and **only** on that application's permitted fields. If a lender's criterion uses a field the application does not permit, the application is **excluded**.
5. Lender criteria may reference only fields from the platform's **allowlistable field catalogue**.
6. Matching runs exclusively on **PublishedProfiles** (frozen permitted fields), never on live Intelligence data ([ADR-0026](0026-published-profile-snapshots.md)).
7. **Full access** requires a separate, lender-specific SME approval; the approved additional fields are frozen as a lender-specific profile at approval time.
8. **Revocation** blocks further reads and matching immediately; the UI states that copies already received cannot be recalled.
9. The SME sees a **"what lenders see" preview** before publishing; the default allowlist is the summary set (industry, amount band, term, assessment category, Data Confidence band).

## Alternatives considered

| Option | Why not |
|---|---|
| Consent in Identity | Remote consent checks on every query, or stale copies; non-atomic publication |
| Hide values only in the UI | Filters, counts and ranking still leak |
| Match on all fields, show only permitted ones | Ranking position leaks hidden values |

## Consequences

**Positive**: privacy by design; immediate revocation; trust argument for SMEs and fiduciaries.
**Negative**: restrictive SMEs get fewer matches; more complex queries.

## Compliance

- FF-C2 indirect-disclosure suite.
- Tests for revocation, full-access approval and denial.
- Marketplace query functions require the lender context and apply consent filters (RLS policies include disclosure checks where feasible).

## Revisit when

Lenders need richer search (consider banded values or SME-approved templates); or legal review adds consent expiry.

## Addendum (2026-11-19): consent revocation across all services

Revocation must be effective everywhere:
- **Marketplace:** immediate through row-level security (a revoked disclosure closes the lender's access in the same transaction).
- **Delegation revocation** (fiduciary): `identity.delegation.revoked` adds a deny-list entry (user, organization, on-behalf-of, since); tokens issued before `since` stop working at every service.
- **Notification:** lender-facing notices that refer to the revoked access are withdrawn.
