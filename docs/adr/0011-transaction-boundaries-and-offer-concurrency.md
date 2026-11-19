# ADR-0011: Transaction Boundaries and Offer-Selection Concurrency

| | |
|---|---|
| **Status** | Proposed — formalizes Architecture Plan v1 §5.1, extended with fee recording |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0004](0004-single-postgresql-and-table-ownership.md), [ADR-0013](0013-billing-and-sme-charging.md), [ADR-0023](0023-in-process-domain-events.md) |

## Context

Selecting an offer changes the offer, the application, possibly a fee charge, and the audit log. Two users (or a double-click) could select different offers at the same time.

## Decision

1. **One transaction per use case.** The top-level application service opens a unit of work; other modules' `api.py` functions receive the same session and **never commit** themselves.
2. **No network calls inside transactions** (bexio, LLM, email).
3. **Select offer** (single transaction):
   - `SELECT … FOR UPDATE` on the LoanApplication row;
   - validate: application `PUBLISHED`, offer belongs to it and is `SUBMITTED` (not expired or withdrawn), user is an authorized SME representative;
   - set offer `SELECTED`, application `OFFER_SELECTED`;
   - `billing.api.record_charge(trigger=OFFER_SELECTED, …)` for every active fee rule with that trigger ([ADR-0013](0013-billing-and-sme-charging.md));
   - `access.api.record_audit(...)`;
   - commit; then dispatch `OfferSelected` events ([ADR-0023](0023-in-process-domain-events.md)).
4. **Database invariant as a second layer:** partial unique index `UNIQUE (application_id) WHERE status = 'SELECTED'` on `lending.loan_offer`.
5. **Offers are immutable** after submission; changed terms mean a new offer. Invalid or conflicting transitions return **409 Conflict**.
6. Other atomic use cases: publish application (state + DataDisclosure + audit + publication fee charge if configured); submit offer (offer + audit); persist import batch; create snapshot (+ metrics + versions); create assessment.

## Alternatives considered

| Option | Why not |
|---|---|
| Application-level check only | Race conditions under concurrency. |
| Optimistic locking only | Works, but the row lock is simpler to reason about here; the unique index is the safety net either way. |
| Sagas / eventual consistency | Unnecessary inside one database. |

## Consequences

**Positive**: exactly one selected offer, fee and audit always consistent.
**Negative**: short row locks on the application during selection (negligible at our volume).

## Compliance

- A concurrency integration test fires two parallel selections: exactly one succeeds, the other gets 409.
- A test injects a failure in `record_charge` and asserts that the selection rolls back.
- Architecture test: repositories do not call `commit()`.

## Revisit when

Modules are extracted into separate services (requires an outbox or saga).
