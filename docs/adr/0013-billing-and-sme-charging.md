# ADR-0013: Billing Service — One-off Company Unlock Fee, Lender Success Fee; Versioned Price Books; Signed Quotes; Charges Exactly as Quoted

| | |
|---|---|
| **Status** | Proposed — supersedes "SME access: free" (Master Plan v1 §2.2) |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0002](0002-service-decomposition.md), [ADR-0011](0011-consistency-model.md), [ADR-0014](0014-no-loan-money-flow.md), [ADR-0015](0015-money-and-financial-calculations.md), [ADR-0019](0019-organization-types-and-delegation.md), [ADR-0021](0021-matching-neutrality.md), [ADR-0023](0023-event-driven-integration.md) |

## Context

- **Team decision (2026-11-19): SMEs will be charged.** The amount and the trigger are still open.
- Candidate models (decided: success-only SME fee, see Decision):
  - Basic / Light / Pro tiers (Seb), not chosen;
  - an SME success fee (Gruber, 2 % example);
  - the lender success fee of 0.75 %, min CHF 2,000, cap CHF 7,500 (pitch deck; to be reconfirmed);
  - a fiduciary referral share of 20 %.
- Fees must be **shown before** the payer commits, charged **exactly**, never lost or duplicated, and must **never influence ranking**.
- In the service-based design, Billing is a separate service; the triggering actions happen in Marketplace.

## Decision

**Current model (team decision 2026-11-23, supersedes the success-only SME fee below)**
- **Companies pay a one-off CHF 190 per loan request** to unlock the identities of the lenders that made offers. It covers the partner identity check. There is no refund and no success fee for the company.
- Offers, ratings and the fair-rate range are visible **before** paying; lender names and the ability to choose an offer need the unlock ([ADR-0032](0032-unlock-payment-and-identity-check.md)).
- **Lenders pay a success fee** (demo: 0.75 %, min CHF 2,000, cap CHF 7,500) when they confirm the payout. It is fixed with a signed quote at offer submission, is never added to the company's cost, and keeps the 14-day dispute window (held on dispute, cancelled if the loan is cancelled). A fiduciary referral share applies to CredSort's fees.
- Everything below about quotes, price books, charges and the 14-day window still applies; the SME success-fee rule is simply not part of the price book any more.

**Earlier decisions (2026-11-19), kept for history**
- **The SME fee is success-only.** There is no publication fee and no subscription plan; every feature is included. A fee becomes **payable only when the loan is funded**.
- **The lender confirms the payout** in the Marketplace (`marketplace.loan.funded`). The SME then has a **14-day dispute window**; the charge is payable after that window.
- The fee amount is still open and stays configuration (price book).
- CredSort never touches loan money ([ADR-0014](0014-no-loan-money-flow.md)); it records only that a loan was funded.

**Model (Billing database)**

| Concept | Description |
|---|---|
| `PriceBook` | Versioned set of rules; `effective_from`; immutable once active; one active version at a time |
| `FeeRule` | `payer` (SME / LENDER), `trigger` (`LOAN_FUNDED` only in the MVP), `calculator` plug-in (`FIXED`, `PERCENT_OF_PRINCIPAL` with min/cap), currency CHF, `tax_code` |
| `Entitlement` | Features an organization may use; default for every SME: profile, apply, advisor, what-if |
| `Quote` | **Signed** (RS256 JWS) statement: subject (offer ID), payer, basis, amount, price-book version, expiry. Consumable once. Status `UNPRICED` when no active price book exists. |
| `FeeCharge` | Immutable ledger entry created **exactly as quoted**; unique per quote; states `PENDING → PAYABLE`, `HELD` (dispute), `CANCELLED` (loan cancelled); corrections via reversal entries |
| `ReferralShare` | 20 % share of a charge attributed to the referring fiduciary |

**Flow**
1. When a lender **submits an offer**, Marketplace requests a quote from Billing (`POST /internal/v1/quotes`, fixed call inventory entry) and stores the quote on the offer. The SME sees the expected fee next to each offer ("payable only if the loan is funded").
2. Selecting an offer **locks** the quote. Marketplace verifies it **locally** (Billing's signature via JWKS, expiry, binding to offer, subject and payer) inside its transaction. No remote call happens inside a transaction.
3. The lender confirms the payout (`marketplace.loan.funded`). Billing consumes the event and records the charge **equal to the quote** (inbox + unique `quote_id`, so a RabbitMQ redelivery cannot create a second fee). `payable_after = funded_at + 14 days`.
4. If the SME disputes within 14 days, `marketplace.loan.disputed` sets the charge to `HELD`. If the loan is cancelled, `marketplace.loan.cancelled` sets it to `CANCELLED`.
5. **Fail closed:** without a valid quote (Billing unavailable at offer submission), the offer cannot be submitted. Billing outages after submission do not affect selection or funding; events are retried over hours (see [ADR-0007](0007-resilience.md)).
6. **Amounts are configuration.** Until the team decides, there is no active price book and the UI shows "fee to be confirmed". Changing a price = activating a new price-book version. A clearly marked **demo placeholder** price book can be activated by an operator for demos only.
7. The lender fee remains a configurable rule; whether it is active is a business decision.
8. **No payment collection in the MVP:** charges are exported for invoicing; a `PaymentProvider` plug-in follows in the pilot ([ADR-0003](0003-plug-in-extension-points.md)).
9. Entitlement changes are published (`billing.entitlements.changed`) and cached by Intelligence and Advisory.

## Alternatives considered

| Option | Why not |
|---|---|
| Marketplace computes fees with a shared pricing library | Duplicates pricing logic across services; Billing is no longer the single source of truth |
| Synchronous charge call from Marketplace inside the transaction | A remote call inside a transaction; Billing outages would break selection |
| Charge first, quote later | Undisclosed fees; integrity and trust violation |
| Subscription-billing SaaS now | Premature before the model is decided; vendor dependency |

## Consequences

**Positive**: pricing decided late without code changes; quote = charge by construction; Billing outages do not affect actions with valid cached quotes.
**Negative**: quote caching and expiry handling in the UI; fee-bearing actions fail closed when no valid quote exists.

## Compliance

- FF-E1: changing an amount = a new price-book version, zero code change.
- FF-I5: recorded charge equals the quote for every fee-bearing action.
- Reconciliation: every funded loan has exactly one charge equal to its quote ([ADR-0011](0011-consistency-model.md)).
- Neutrality: Marketplace matching code cannot access quotes or prices ([ADR-0021](0021-matching-neutrality.md)).

## Revisit when

The team decides the SME fee (activate a price book; no ADR needed unless a new trigger or calculator type is required); payment collection is needed; or legal review requires changes.
