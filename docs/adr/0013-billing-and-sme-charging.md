# ADR-0013: Billing Module — SMEs Are Charged; Pricing Is Versioned Configuration

| | |
|---|---|
| **Status** | Proposed — **supersedes** "SME access: free" (Master Plan v1 §2.2) |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0002](0002-six-domain-modules.md), [ADR-0011](0011-transaction-boundaries-and-offer-concurrency.md), [ADR-0014](0014-no-loan-money-flow.md), [ADR-0015](0015-money-and-financial-calculations.md), [ADR-0019](0019-organization-types-and-delegation.md), [ADR-0021](0021-matching-neutrality.md) |

## Context

- **Team decision (2026-11-19): SMEs will be charged.** The amount and the trigger will be decided later.
- Candidate models on the table:
  - Basic (free) / Light (one-off fee per financing request) / Pro (annual subscription) — Seb, Business Model canvas;
  - an SME success fee at disbursement (2 % example) — Gruber §3;
  - the lender success fee of 0.75 %, min CHF 2,000, cap CHF 7,500, disclosed to the SME — pitch deck; to be reconfirmed;
  - a fiduciary referral share of 20 % of CredSort's fee.
- Fees must be **disclosed before** the SME (or lender) commits, must be **exact**, and must **never influence ranking**.
- No payment infrastructure is needed for the MVP (Master Plan §2.2).

## Decision

We introduce the **`billing` module** with a configuration-driven model.

**Model**

| Concept | Description |
|---|---|
| `PriceBook` | Versioned set of fee rules and plans with `effective_from`; **immutable once active**; exactly one active version per segment and date |
| `FeeRule` | `code`, `payer` (SME / LENDER), `trigger` (`PLAN_SUBSCRIPTION`, `APPLICATION_PUBLISHED`, `OFFER_SELECTED`, `MANUAL`), `calculation` (`FIXED` amount, or `PERCENT_OF_PRINCIPAL` with optional `min` / `cap`), `currency` (CHF), `tax_code` |
| `Plan` | e.g. Basic, Light, Pro; a set of `Entitlement`s and any subscription `FeeRule` |
| `Entitlement` | Feature flag unlocked by a plan (e.g. `WHAT_IF_ANALYSIS`, `REFINANCING_ALERTS`) |
| `FeeCharge` | **Immutable** ledger entry: payer org, rule + price-book version, basis amount, computed amount, trigger reference (application/offer id), status (`RECORDED`, `INVOICED`, `PAID`, `WAIVED`). Corrections are **reversal entries**, never updates. |
| `ReferralShare` | Share of a charge attributed to the referring fiduciary (rule-based, e.g. 20 %) |

**Behaviour**

1. `billing.api.quote(trigger, context)` returns the fees an action *will* cause. The UI shows the quote **before** the action (screens S2, S8, L5).
2. `billing.api.record_charge(trigger, context)` is called **inside the same transaction** as the triggering business action ([ADR-0011](0011-transaction-boundaries-and-offer-concurrency.md)).
3. `billing.api.has_entitlement(org, feature)` gates plan features.
4. **Amounts are not hard-coded.** Until the team decides, the seed contains a `DRAFT` price book with placeholder rules, and the UI shows "fee to be confirmed". Changing a price means activating a new version, never a code change.
5. The lender success fee is kept as a **configurable rule**; whether it stays active is a business decision.
6. **No payment collection in the MVP:** charges are recorded and can be exported. A `PaymentProvider` port (e.g. an invoicing service supporting Swiss QR-bills) is added for the pilot.
7. VAT treatment is stored as a `tax_code` on the rule; the rates and obligations are to be clarified with an accountant.

## Alternatives considered

| Option | Why not |
|---|---|
| Hard-code fees in `lending` | Every pricing decision becomes a code change; neutrality is harder to prove. |
| Integrate a subscription-billing SaaS now | Overkill before the model is decided; adds a vendor dependency and breaks offline demos. |
| Mutable charge records | Loses the audit trail; violates data integrity. |

## Consequences

**Positive**: the team can decide or change pricing late; fees are transparent and auditable; supports tiers, success fees, lender fees and referral shares.
**Negative**: more modelling up front; the UI must handle "TBD" states; a price-book admin screen is needed (A2).

## Compliance

- Test: changing an amount = activating a new PriceBook version, with **zero code change**; old charges keep their original rule version.
- Test: the quote shown equals the charge recorded for the same inputs.
- Test: a failing `record_charge` rolls back the triggering action.
- import-linter: `lending.domain.matching` must not import `billing` ([ADR-0021](0021-matching-neutrality.md)).

## Revisit when

The team decides the SME fee (activate a price book; no new ADR needed unless the model needs a new trigger or calculation type); payment collection is needed (pilot); or a regulatory review of the fee model requires changes.
