# ADR-0019: Organization Types, Fiduciary Delegation and Referral Attribution Modelled Now

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0002](0002-six-domain-modules.md), [ADR-0008](0008-consent-and-permitted-field-matching.md), [ADR-0013](0013-billing-and-sme-charging.md), [ADR-0017](0017-tenant-isolation.md) |

## Context

- Fiduciaries (Treuhänder) are described as **the main acquisition channel** in the Business Model canvas, as "fiduciary-first distribution" in the Brainstorming USPs and in the Master Plan, and as a lever for both sides by Gruber.
- They earn a **20 % share** of CredSort's fee for referred SMEs.
- The fiduciary portal itself is P2.
- Attribution cannot be reconstructed later: if the first SMEs are onboarded without recording who referred them, the revenue share cannot be computed.

## Decision

1. `Organization.type ∈ {SME, LENDER, FIDUCIARY, PLATFORM}` from the first migration.
2. Roles per type: `SME_ADMIN`, `SME_MEMBER`, `LENDER_ADMIN`, `CREDIT_OFFICER`, `FIDUCIARY_ADVISOR`, `PLATFORM_ADMIN`. Only `SME_ADMIN` (or an explicitly authorized member) can publish applications, grant disclosure and select offers.
3. **Delegation** (in `access`): an SME admin can grant a fiduciary organization a scoped, revocable delegation (e.g. `PREPARE_APPLICATION`, `VIEW_PROFILE`). Delegation never includes selecting offers or granting lender disclosure. All delegated actions are audited.
4. **Referral attribution:** at onboarding, an SME may enter a referral code; `referred_by_org_id` is stored once and is immutable except by a platform admin (audited). `billing` uses it to compute `ReferralShare`s ([ADR-0013](0013-billing-and-sme-charging.md)).
5. The **fiduciary UI** (client portfolio, portfolio scan, commissions) is built in P2. In the MVP the channel is validated manually, as the Master Plan recommends.

## Alternatives considered

| Option | Why not |
|---|---|
| Add fiduciaries when the P2 portal is built | Attribution history would be lost; authorization would need retrofitting. |
| Fiduciary as a special SME member | Fiduciaries serve many SMEs; a member role per SME does not express a portfolio or a commission. |
| A separate `fiduciary` module now | Premature; the concepts fit `access` and `billing`. |

## Consequences

**Positive**: the GTM channel is supported from day one; no data migration later; a clear authorization model.
**Negative**: a slightly larger access model in the MVP; roles must be tested even before the fiduciary UI exists.

## Compliance

- Authorization tests: a fiduciary without delegation → 404; with delegation → only the delegated actions; never offer selection.
- Test: a referral code captured at onboarding produces a ReferralShare when a charge is recorded.

## Revisit when

The fiduciary portal (P2) starts; or a fiduciary partner requires bulk import of clients.
