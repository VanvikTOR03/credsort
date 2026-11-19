# ADR-0013: Billing Service — SMEs Are Charged; Versioned Price Books; Signed Quotes; Charges Exactly as Quoted

| | |
|---|---|
| **Status** | Proposed — supersedes "SME access: free" (Master Plan v1 §2.2) |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0002](0002-service-decomposition.md), [ADR-0011](0011-consistency-model.md), [ADR-0014](0014-no-loan-money-flow.md), [ADR-0015](0015-money-and-financial-calculations.md), [ADR-0019](0019-organization-types-and-delegation.md), [ADR-0021](0021-matching-neutrality.md), [ADR-0023](0023-event-driven-integration.md) |

## Context

- **Team decision (2026-11-19): SMEs will be charged.** The amount and the trigger are still open.
- Candidate models:
  - Basic / Light / Pro tiers (Seb);
  - an SME success fee (Gruber, 2 % example);
  - the lender success fee of 0.75 %, min CHF 2,000, cap CHF 7,500 (pitch deck; to be reconfirmed);
  - a fiduciary referral share of 20 %.
- Fees must be **shown before** the payer commits, charged **exactly**, never lost or duplicated, and must **never influence ranking**.
- In the service-based design, Billing is a separate service; the triggering actions happen in Marketplace.

## Decision

**Model (Billing database)**

| Concept | Description |
|---|---|
| `PriceBook` | Versioned set of rules and plans; `effective_from`; immutable once active; one active version per segment and date |
| `FeeRule` | `payer` (SME / LENDER), `trigger` (`PLAN_SUBSCRIPTION`, `APPLICATION_PUBLISHED`, `OFFER_SELECTED`, `MANUAL`), `calculator` plug-in (`FIXED`, `PERCENT_OF_PRINCIPAL` with min/cap), currency CHF, `tax_code` |
| `Plan`, `Entitlement` | Basic/Light/Pro-style plans and the features they unlock |
| `Quote` | **Signed** (JWS) statement: action, subject (application or offer ID), payer, basis, amount, price-book version, expiry. Consumable once. |
| `FeeCharge` | Immutable ledger entry created **exactly as quoted**; unique per quote; corrections via reversal entries |
| `ReferralShare` | Share of a charge attributed to the referring fiduciary |

**Flow**
1. When Marketplace shows a fee-bearing action (publish screen, offer composer, offer comparison), it requests quotes from Billing (`POST /internal/v1/quotes`) and caches them until expiry (e.g. 24 h).
2. The payer sees the quoted amount. The action references the quote.
3. Marketplace verifies the quote **locally** (Billing's signature, expiry, binding to the action, subject and payer) inside its transaction and emits the event with `quote_ids` via its outbox.
4. Billing consumes the event and records a charge **equal to the quote** (inbox + unique `quote_id`). A missing, unknown or already-used quote → `billing.charge.held` + alert, never a guessed amount.
5. **Fail closed:** without a valid quote (Billing unavailable and no cached quote), the fee-bearing action is blocked.
6. **Amounts are configuration.** Until the team decides, the seed contains a `DRAFT` price book; the UI shows "fee to be confirmed". Changing a price = activating a new price-book version.
7. The lender success fee remains a **configurable rule**; whether it stays active is a business decision.
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
- Reconciliation: every published application or selected offer with quotes has its charges ([ADR-0011](0011-consistency-model.md)).
- Neutrality: Marketplace matching code cannot access quotes or prices ([ADR-0021](0021-matching-neutrality.md)).

## Revisit when

The team decides the SME fee (activate a price book; no ADR needed unless a new trigger or calculator type is required); payment collection is needed; or legal review requires changes.
