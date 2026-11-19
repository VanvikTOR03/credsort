# ADR-0010: Background Import Recovery and Idempotency

| | |
|---|---|
| **Status** | Proposed — formalizes Architecture Plan v1 §5.2 (new ADR in its register) |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0005](0005-sync-use-cases-and-background-import.md), [ADR-0015](0015-money-and-financial-calculations.md) |

## Context

Imports run in-process ([ADR-0005](0005-sync-use-cases-and-background-import.md)). A restart can interrupt a job. Users may double-click, retry, or start parallel imports. Financial data must never be duplicated or partially written.

## Decision

**Recovery (single backend process)**
- On startup, every `PENDING` or `RUNNING` job is marked `FAILED` with reason `interrupted`.
- A manual retry creates a **new** job; failed jobs are never resumed in place.
- This rule is valid **only while one process runs jobs**. When a separate worker or several instances are introduced, replace it with a lease/heartbeat (`locked_until`) mechanism.

**Idempotency and atomicity**
- External pages are fetched **outside** DB transactions; the validated result is written **atomically** (ImportBatch + canonical entries in one transaction).
- At most **one active job per DataConnection** (partial unique index on `connection_id WHERE status IN ('PENDING','RUNNING')`).
- An ImportBatch is unique per normalization key: `(connection_id, period, content_hash, mapping_version)`. Re-importing identical data creates no new batch.
- A new FinancialSnapshot is created only after successful validation. The previous snapshot stays current on failure.

## Alternatives considered

| Option | Why not |
|---|---|
| Lease/heartbeat scheduler now | More complexity than one process needs. |
| Content hash alone for deduplication | Not sufficient against concurrent imports and partial writes. |
| Resume interrupted jobs | Complex checkpointing; a re-run is cheap at our volumes. |

## Consequences

**Positive**: no duplicated or half-written financial data; simple semantics.
**Negative**: users must re-trigger interrupted imports; the rule must change when scaling out.

## Compliance

- Tests: process restart during RUNNING → FAILED; duplicate submission → one job; identical re-import → no new batch; parallel import attempt → 409.

## Revisit when

A separate worker process or several backend instances are introduced ([ADR-0024](0024-deployment-and-demo-modes.md), pilot stage).
