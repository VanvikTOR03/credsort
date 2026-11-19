# ADR-0023: Event-Driven Integration — Transactional Outbox, RabbitMQ, Idempotent Inbox, Thin Events

| | |
|---|---|
| **Status** | Proposed — replaces "in-process domain events" (Revision 1) |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0001](0001-architecture-style.md), [ADR-0011](0011-consistency-model.md), [ADR-0006](0006-api-contracts.md), [06 §3](../architecture/06-runtime-and-integration.md) |

## Context

Services must react to each other's facts (import completed → pipeline; loan funded → charge; loan disputed → charge held; membership revoked → deny-list) without synchronous coupling, without losing events, and without duplicate effects. Events must not spread confidential data.

## Decision

1. **Transactional outbox** in every producing service: the event row is written in the same DB transaction as the state change. A relay publishes it to RabbitMQ with **publisher confirms** and marks it sent only after the confirm.
2. **Broker:** RabbitMQ, topic exchange `credsort.events`, **quorum queues** per consumer, delayed retry queues, a **dead-letter queue** per consumer.
3. **Idempotent inbox** in every consumer: `(consumer, event_id)` unique, written in the same transaction as the side effect.
4. **Envelope:** CloudEvents 1.0 JSON with `credsortorgid`, `credsortaggregateversion` and `traceparent` extensions ([06 §3.1](../architecture/06-runtime-and-integration.md)).
5. **Thin events:** IDs, states, versions only. No ledger data, metrics, profile values or personal data. Consumers needing details use the **claim-check** pattern via authorized internal APIs.
6. **Ordering:** not assumed; consumers ignore events whose aggregate version is older than the one they hold.
7. **Schemas:** JSON Schema per event type in `contracts/events/`; additive changes within a major version; breaking changes publish `v2` alongside `v1`.
8. **Retention and replay:** outbox rows retained ≥ 35 days; a replay tool re-publishes by time range or aggregate; consumers skip tombstoned (deleted) organizations ([ADR-0031](0031-data-lifecycle-and-deletion.md)).
9. **Only the outbox library may publish**; no direct broker publishing from handlers (no dual writes).
10. Notifications and the central audit log are fed by these events (Notification and Audit services).

## Alternatives considered

| Option | Why not |
|---|---|
| Kafka (log-based) | Replay is attractive, but long retention of event streams duplicates data; our volumes don't need it; outbox retention covers replay |
| Publishing directly after commit | Lost events on crash (dual-write problem) |
| Fat events with full data | Spreads confidential data into the broker, DLQs and every consumer |
| Synchronous calls instead of events | Couples availability; creates dependency cycles |

## Consequences

**Positive**: no lost or duplicated effects; loose coupling; confidential data stays with its owner.
**Negative**: eventual consistency; operating a broker; outbox/inbox tables in every service; claim-check calls add load on owners.

## Compliance

FF-I4 (duplicate and out-of-order delivery), FF-C5 (event schema scan), architecture test (no broker client outside the relay), FF-E4 (schema compatibility), outbox-lag and DLQ alerts.

## Revisit when

Event volume or replay needs outgrow RabbitMQ; or an external partner needs event subscriptions (design a partner event API).
