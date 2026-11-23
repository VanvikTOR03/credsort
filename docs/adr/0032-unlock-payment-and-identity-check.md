# ADR-0032: One-off Unlock Payment, Payment Gateway Port and Partner Identity Check

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-23 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0003](0003-plug-in-extension-points.md), [ADR-0013](0013-billing-and-sme-charging.md), [ADR-0020](0020-kyb-outsourced-via-port.md), [ADR-0023](0023-event-driven-integration.md) |

## Context

The team decided that companies pay a one-off CHF 190 per loan request. It covers the identity check done by a verification partner each time. Offers must stay visible before paying so the company can judge the value; only the lender identities and the choice are gated.

## Decision

1. **Unlock payment (Billing).** `POST /v1/unlock/payments {application_id, method}` charges the price of the active price-book rule with trigger `OFFERS_UNLOCKED` (payer SME, `FIXED`). Only an SME admin (not a delegate) can pay. One payment per application (unique); a retry returns the first payment and never charges twice. Billing emits `billing.unlock.paid` through its outbox. The price is public (`GET /v1/unlock/price`) and shown before paying. No rule = no price = no payment.
2. **Payment gateway port.** Billing calls a `PaymentGateway` plug-in. The MVP ships a **demo gateway** that supports TWINT, Visa and Mastercard and always approves, moving no money and accepting no card details; it is **refused in production**. A real provider implements the same port and hosts its own card form, so card numbers never reach CredSort. The gateway call happens outside any database transaction.
3. **Marketplace reveals lenders.** Marketplace consumes `billing.unlock.paid` and sets `applications.unlocked_at` (idempotent, only for the owning organization). Until then the offers API returns masked names ("Lender A"), not the real identity, and **selecting an offer is refused** (`not_unlocked`). The mask is applied on the server; the browser never receives the name.
4. **Partner identity check (Identity).** Identity consumes `billing.unlock.paid` and runs the `IdentityProvider` port (`verify_identity`), stores `kyc_status` (`NONE | VERIFIED | REJECTED`), and emits `identity.organization.kyc_completed`. The MVP stub approves a well-formed UID; a real partner replaces it behind the port.
5. **Notification** tells the company that offers are unlocked and when the identity check finished (no values).
6. The unlock fee is **not refunded** if the request is withdrawn or no offer suits the company.

## Alternatives considered

| Option | Why not |
|---|---|
| Hide offers entirely until paid | The company cannot judge the value of paying; weaker trust |
| Gate on a synchronous Billing call from Marketplace | Couples availability; the event flow already guarantees delivery |
| Take card details in CredSort | PCI scope and risk; a hosted provider form avoids it |

## Consequences

**Positive**: revenue is collected before the lender identities are shown; the identity check runs once per paid request; the gateway and the identity provider are swappable.
**Negative**: a short delay between payment and visible unlock (eventual consistency, usually under a second); the demo gateway must never be mistaken for a real one.

## Compliance

- FF: the demo gateway and the dev shortcuts are refused in production (fitness tests).
- Tests: payment idempotency, unlock event idempotency and ownership, locked offers never contain the lender name, selection requires the unlock.

## Revisit when

A real payment provider and identity partner are contracted (data-processing agreements, regions), or the price model changes.
