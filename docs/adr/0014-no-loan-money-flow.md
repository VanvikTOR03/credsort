# ADR-0014: CredSort Never Holds or Moves Loan Money

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0013](0013-billing-and-sme-charging.md), [ADR-0001](0001-modular-monolith.md) |

## Context

- The Business Model canvas states: "CredSort never lends, so it carries no credit risk and needs no balance sheet."
- Gruber §3 suggests a **servicing fee over the loan's lifetime for payment processing, reporting and collections**. Taken literally, CredSort would receive and forward repayments.
- Accepting, holding or transferring third-party funds is **likely** to qualify CredSort as a financial intermediary under Swiss anti-money-laundering law and may raise further licensing questions. **This must be confirmed by a legal review.** In any case it would add payment reconciliation, a money ledger and much stricter security and operations requirements.

## Decision

1. CredSort **never** lends, never holds client money, and never receives, holds or forwards loan principal, interest or repayments.
2. Loan contracts, bank-side KYC, disbursement and repayment happen **directly between lender and SME**.
3. CredSort only **invoices its own fees** ([ADR-0013](0013-billing-and-sme-charging.md)).
4. Gruber's servicing idea is **not adopted in that form**. A recurring fee is acceptable for services that do not touch funds (monitoring, annual re-rating, reporting to the lender, refinancing alerts).
5. Any future servicing or payment feature would go through a **licensed partner** behind a port, after legal review, and requires a new ADR.

## Alternatives considered

| Option | Why not |
|---|---|
| CredSort collects repayments and forwards them | Likely regulated activity; a money ledger, reconciliation and operational risk far beyond MVP scope. |
| Escrow of fees from the loan amount | Same issue: CredSort touches loan funds. |

## Consequences

**Positive**: a much smaller regulatory and security surface; no balance sheet; simpler architecture.
**Negative**: one revenue idea (servicing on payment flows) is off the table unless partnered; the success fee must be invoiced and collected separately.

## Compliance

- No data model, API or adapter for disbursements, repayments or client-money accounts. Adding one requires a new ADR and a legal review.
- Demo script and UI text state that the loan is concluded with the lender.

## Revisit when

The business wants servicing revenue → legal review + licensed partner evaluation.
