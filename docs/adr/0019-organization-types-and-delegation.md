# ADR-0019: Organization Types, Fiduciary Delegation and Referral Attribution from Day One

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0002](0002-service-decomposition.md), [ADR-0013](0013-billing-and-sme-charging.md), [ADR-0017](0017-tenant-isolation.md), [ADR-0027](0027-context-tokens-and-service-trust.md) |

## Context

- Fiduciaries (Treuhänder) are **the main acquisition channel** (Business Model canvas, Brainstorming, Master Plan, Gruber) and earn a **20 % share** of CredSort's fee for referred SMEs.
- The fiduciary portal is P2, but attribution cannot be reconstructed later. Without a record of who referred the first SMEs, the revenue share cannot be computed.

## Decision

1. `Organization.type ∈ {SME, LENDER, FIDUCIARY, PLATFORM}` in Identity from the first migration.
2. Roles: `SME_ADMIN`, `SME_MEMBER`, `LENDER_ADMIN`, `CREDIT_OFFICER`, `FIDUCIARY_ADVISOR`, `PLATFORM_ADMIN`. Only `SME_ADMIN` (or an explicitly authorized member) publishes applications, grants disclosure and selects offers.
3. **Delegation** (Identity): an SME admin grants a fiduciary organization scoped, revocable rights (e.g. `VIEW_PROFILE`, `PREPARE_APPLICATION`). Delegation **never** includes selecting offers or granting lender disclosure.
4. Delegations appear in the **context token** (`on_behalf_of`, scopes) so every service can enforce them without calling Identity ([ADR-0027](0027-context-tokens-and-service-trust.md)). Every delegated action is audited with both the acting and the represented organization.
5. **Referral attribution:** at onboarding an SME may enter a referral code; `referred_by_org_id` is stored once and is immutable except by an audited platform-admin correction. `identity.organization.created` carries it; Billing computes `ReferralShare`s.
6. The **fiduciary UI** comes in P2; in the MVP the channel is validated manually.

## Alternatives considered

| Option | Why not |
|---|---|
| Add fiduciaries with the P2 portal | Attribution history lost; authorization retrofitted |
| Fiduciary as a member of each SME | Cannot express a portfolio or a commission |
| A separate Fiduciary service | Premature; the concepts fit Identity and Billing |

## Consequences

**Positive**: the go-to-market channel works from day one; no later migration.
**Negative**: a richer authorization model in the MVP; delegation scopes must be tested before the portal exists.

## Compliance

- Authorization tests: a fiduciary without delegation → 404; with delegation → only delegated actions; never selection or disclosure.
- Test: a referral code at onboarding produces a ReferralShare when a charge is recorded.

## Revisit when

The fiduciary portal starts; or partners need bulk client onboarding.
