# ADR-0023: In-Process Domain Events After Commit; Critical Writes Stay in the Transaction

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0001](0001-modular-monolith.md), [ADR-0002](0002-six-domain-modules.md), [ADR-0011](0011-transaction-boundaries-and-offer-concurrency.md) |

## Context

Several flows need side effects in other modules: "new offer available" notifications, removing a revoked application from matching, Pro-tier refinancing alerts, benchmark refresh. Upstream modules must not call downstream modules (no cycles, [ADR-0002](0002-six-domain-modules.md)), and there is no message broker ([ADR-0001](0001-modular-monolith.md)).

## Decision

1. Modules publish **domain events** (immutable dataclasses, e.g. `OfferSubmitted`, `OfferSelected`, `DisclosureRevoked`, `ImportCompleted`) to an **in-process dispatcher** in `shared`.
2. Events are collected during the unit of work and dispatched **only after a successful commit**. Handlers run in their own transaction.
3. **Only best-effort side effects use events**: notifications, read-model or cache refreshes, triggering a follow-up job. A failing handler is logged and retried a bounded number of times, but never undoes the original action.
4. **Writes that must be atomic** with the business action (fee charges, audit events, disclosure records) are **not** events. They are synchronous calls to the owner's `api.py` inside the same transaction ([ADR-0011](0011-transaction-boundaries-and-offer-concurrency.md)).
5. Notifications are stored **in-app** (a table plus the UI). Email comes later through the `Notifier` port.
6. A **transactional outbox** table is introduced only when external side effects (email, payment provider) need delivery guarantees.

## Alternatives considered

| Option | Why not |
|---|---|
| Message broker (RabbitMQ/Kafka) | Infrastructure and eventual consistency without need. |
| Direct calls from upstream to downstream modules | Creates dependency cycles. |
| Events for fee charges | A lost event = a lost charge, which is an integrity defect. |

## Consequences

**Positive**: decoupled side effects without infrastructure; critical data stays consistent.
**Negative**: after-commit handlers can be lost on a crash (acceptable for notifications); developers must classify each side effect correctly.

## Compliance

- Review rule: every new event handler states "best-effort" in its docstring; anything that must not be lost uses a transactional call instead.
- Test: a failing handler does not roll back the triggering action.

## Revisit when

Email or payment-provider integration requires guaranteed delivery (add an outbox); or modules are extracted into services.
