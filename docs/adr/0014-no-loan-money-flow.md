# ADR-0014: CredSort Never Holds or Moves Loan Money

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0013](0013-billing-and-sme-charging.md), [ADR-0001](0001-architecture-style.md) |

## Context

- Business Model canvas: "CredSort never lends, so it carries no credit risk and needs no balance sheet."
- Gruber §3 suggests a **servicing fee over the loan's lifetime for payment processing, reporting and collections**. Taken literally, CredSort would receive and forward repayments.
- Accepting, holding or transferring third-party funds is **likely** to qualify CredSort as a financial intermediary under Swiss anti-money-laundering law and may raise further licensing questions. **This must be confirmed by a legal review.** It would also add a money ledger, payment reconciliation and much stricter security and operations requirements.

## Decision

1. CredSort **never** lends, never holds client money, and never receives, holds or forwards loan principal, interest or repayments.
2. Loan contracts, bank-side KYC, disbursement and repayment happen **directly between lender and SME**.
3. CredSort only **invoices its own fees** ([ADR-0013](0013-billing-and-sme-charging.md)).
4. Gruber's servicing idea is **not adopted in that form**. Recurring fees are acceptable for services that do not touch funds: monitoring, annual re-rating, reporting to the lender, refinancing alerts.
5. Any future servicing or payment feature goes through a **licensed partner** behind a plug-in, after legal review, and requires a new ADR.

## Alternatives considered

| Option | Why not |
|---|---|
| Collect repayments and forward them | Likely regulated activity; a money ledger and operational risk far beyond scope |
| Deduct fees from the loan amount (escrow) | CredSort would touch loan funds |

## Consequences

**Positive**: a much smaller regulatory and security surface; no balance sheet.
**Negative**: servicing revenue on payment flows is off the table unless partnered; fees are invoiced and collected separately.

## Compliance

- No data model, API, event or plug-in for disbursements, repayments or client-money accounts. Adding one requires a new ADR and a legal review.
- UI and demo script state that the loan is concluded with the lender.

## Revisit when

The business wants servicing revenue → legal review + licensed-partner evaluation.
