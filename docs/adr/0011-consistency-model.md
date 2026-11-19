# ADR-0011: Consistency Model — Strong Inside a Service, Guaranteed-Eventual Across Services

| | |
|---|---|
| **Status** | Proposed — extends v1 §5.1 (transaction boundaries, offer concurrency) to the service-based design |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0004](0004-database-per-service.md), [ADR-0013](0013-billing-and-sme-charging.md), [ADR-0023](0023-event-driven-integration.md), [06 §5](../architecture/06-runtime-and-integration.md), [07 §1](../architecture/07-failure-modes-and-risks.md) |

## Context

With a database per service there are no cross-service transactions. Integrity is a driving characteristic, so every flow must declare its consistency level and how it is guaranteed.

## Decision

**1. Invariants that must hold atomically live inside one service's transaction**

| Use case | Service | Atomic contents |
|---|---|---|
| Publish application | Marketplace | State → PUBLISHED, PublishedProfile, DataDisclosure, quote reference, local audit, outbox |
| Submit offer | Marketplace | Immutable offer, accepted lender quote reference, audit, outbox |
| **Select offer** | Marketplace | `SELECT … FOR UPDATE` on the application; validate states, ownership, role, quote validity; offer SELECTED; application OFFER_SELECTED; audit; outbox |
| Revoke disclosure | Marketplace | `revoked_at`, profile access closed, audit, outbox |
| Persist import | Accounting | ImportBatch + entries + outbox |
| Pipeline result | Intelligence | Snapshot + metrics + assessment + inbox + outbox |
| Record charge | Billing | Charge + referral share + inbox + outbox |

Database guarantees as the second layer: partial unique index `UNIQUE (application_id) WHERE status = 'SELECTED'`; unique `quote_id` on charges; unique inbox entries.

**2. Cross-service effects are eventual but guaranteed**: transactional outbox → broker with publisher confirms → idempotent inbox ([ADR-0023](0023-event-driven-integration.md)). No distributed transactions, no two-phase commit, no compensating sagas for core flows.

**3. Reconciliation jobs** run daily (hourly in the pilot) and alert on any mismatch:
- every `offer.selected` / `application.published` with quotes ↔ Billing charges;
- every ImportBatch ↔ a snapshot or a recorded pipeline failure;
- local audit counts ↔ central audit counts per service; hash-chain verification.

**4. Projections** of other services' data are listed with staleness bounds and rebuild procedures ([03 §6](../architecture/03-domain-model.md)).

**5. No synchronous remote calls inside transactions.** Needed remote data (profile extract, quotes) is fetched before the transaction and validated inside it (immutable IDs, signatures, expiry).

## Alternatives considered

| Option | Why not |
|---|---|
| Distributed transactions (2PC) | Couples availability of all participants; poor support; contradicts service autonomy |
| Sagas for selection | Unnecessary: the selection invariant fits inside Marketplace |
| Best-effort events without outbox | Lost fees and snapshots on crashes |

## Consequences

**Positive**: hard invariants are enforced by one database; everything else converges and is checked.
**Negative**: fees, snapshots and the central audit log lag by seconds; reconciliation must be operated.

## Compliance

FF-I3 (concurrent selection), FF-I4 (duplicate delivery), FF-I5 (quote = charge), FF-I6 (reconciliation = zero mismatches), FF-I7 (audit chain).

## Revisit when

A new requirement needs atomicity across two services (first try to move the boundary; only then consider a saga with an ADR).
