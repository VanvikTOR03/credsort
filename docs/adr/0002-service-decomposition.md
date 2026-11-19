# ADR-0002: Service Decomposition and Boundaries

| | |
|---|---|
| **Status** | Proposed — replaces the five/six-module decision of Architecture Plan v1 §3 and Revision 1 |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0001](0001-architecture-style.md), [03-domain-model.md](../architecture/03-domain-model.md), [ADR-0008](0008-consent-and-permitted-field-matching.md), [ADR-0013](0013-billing-and-sme-charging.md) |

## Context

Service boundaries decide where data lives (confidentiality), which invariants can be enforced in one transaction (integrity), and what can change independently (evolvability). Two boundary questions are critical:

1. **Where does consent live?** Matching must check consent on every query, and publication + consent must be atomic.
2. **Where does pricing live?** SMEs will be charged (amount TBD), and fees must never influence ranking.

## Decision

**Domain services**

| Service | Owns | Key reason for the boundary |
|---|---|---|
| **Identity** | Organizations, users (linked to Keycloak), memberships, roles, delegation, referral attribution, KYB status; issues context tokens | One authority for "who acts for whom" |
| **Accounting Integration** | Connections, bexio tokens (only here), import jobs and workers, canonical ledger | Isolates the most sensitive raw data and the least reliable external dependency |
| **Financial Intelligence** | Mappings, snapshots, metrics, scorecards, assessments, Data Confidence, scenarios | Core domain; reproducibility; CPU-bound pipeline |
| **Marketplace** | Applications, **consent (DataDisclosure)**, **published profiles**, lender criteria, matching, offers, selection, rate estimates, benchmark | Keeps every marketplace invariant inside one ACID boundary; consent sits next to matching, so revocation is immediate |
| **Billing** | Price books, fee rules, plans, entitlements, signed quotes, charges, referral shares | Pricing changes independently; physically separate from matching (neutrality) |
| **Advisory** | Explanation cache only | Lets the AI run with no access to financial databases |

**Platform services:** **Notification** (in-app, later email; no financial values) and **Audit** (central, append-only, hash-chained activity log). Plus the **web app + BFF** and the **edge gateway**.

**Explicit boundary decisions**
- **Consent belongs to Marketplace, not Identity.** Consent is about applications and fields, and it must be checked in the same transaction as publication and in the same database as matching.
- **Fiduciaries are not a service.** They are an organization type with delegation (Identity) and referral shares (Billing) ([ADR-0019](0019-organization-types-and-delegation.md)).
- **The benchmark stays in Marketplace** until volume justifies an analytics store ([ADR-0022](0022-offer-data-for-rate-benchmark.md)).

## Alternatives considered

| Option | Why not |
|---|---|
| Consent in Identity (an "access" service) | Every matching query would need a remote consent check or a stale copy; publication + consent would span two databases |
| Billing inside Marketplace | Pricing churn would enter the core; neutrality would be harder to prove |
| Split Marketplace into Applications, Matching and Offers | Turns the selection invariant into a saga (see [ADR-0001](0001-architecture-style.md)) |
| Advisory inside Intelligence | The LLM integration would run in the service holding the most financial data |
| Separate Fiduciary service now | Premature; concepts fit Identity and Billing |

## Consequences

**Positive**: invariants are local; the most sensitive data has the fewest readers; pricing and AI evolve independently.
**Negative**: Marketplace is the largest service and must keep strong internal module boundaries; Identity becomes a shared runtime dependency.

## Compliance

- Each service has its own repository folder, database, credentials, pipeline and OpenAPI document ([ADR-0030](0030-repository-and-shared-libraries.md)).
- Marketplace internal modules (applications, consent, matching, offers, benchmark) are enforced with import rules; `matching` may not import anything billing-related ([ADR-0021](0021-matching-neutrality.md)).
- FF-C8: Advisory has no credentials for financial databases.

## Revisit when

Marketplace grows a part with clearly different characteristics (e.g. benchmark analytics at volume); or the fiduciary portal grows its own data and lifecycle.
