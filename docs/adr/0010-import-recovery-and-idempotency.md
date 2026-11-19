# ADR-0010: Import Job Leasing, Recovery and Idempotency

| | |
|---|---|
| **Status** | Proposed — replaces the single-process recovery rule of v1 §5.2 / Revision 1 |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0005](0005-import-workers.md), [ADR-0015](0015-money-and-financial-calculations.md), [ADR-0025](0025-financial-data-pipeline.md) |

## Context

Imports run on several worker instances ([ADR-0005](0005-import-workers.md)). A worker can crash mid-job; users can double-submit; identical data can be imported twice. Financial data must never be duplicated or partially written.

## Decision

**Leasing and recovery**
- A worker claims a job with `FOR UPDATE SKIP LOCKED` and sets `locked_until = now() + lease` (e.g. 2 min). It renews the lease with heartbeats while working.
- A job whose lease expired without completion is **re-claimable**. After N failed attempts it becomes `FAILED` with the last reason.
- External pages are fetched **outside** transactions; the result is written **atomically** (ImportBatch + entries + outbox event).

**Idempotency**
- At most one active job per DataConnection (partial unique index on `connection_id WHERE status IN ('PENDING','RUNNING')`).
- `POST /v1/import-jobs` accepts an `Idempotency-Key`.
- An ImportBatch is unique per `(connection_id, period, content_hash, normalizer_version)`. Re-importing identical data completes the job without creating a new batch or event.
- A new snapshot is created only from a successfully validated batch. On failure, the previous snapshot stays current.

## Alternatives considered

| Option | Why not |
|---|---|
| "Mark all running jobs failed on startup" (Revision 1) | Wrong with several workers: one worker would fail another worker's active job |
| Resume from checkpoints | Complex; re-running a job is cheap at our volumes |
| Content hash alone | Not sufficient against concurrent imports |

## Consequences

**Positive**: safe with any number of workers; no duplicated or partial data.
**Negative**: lease tuning; a crashed job waits for its lease to expire.

## Compliance

- Tests: worker killed mid-job → job re-claimed after lease expiry and completed once; double submission → one job; identical re-import → no new batch; parallel attempt → 409.

## Revisit when

Job dispatch moves to the broker (lease semantics move to message acknowledgement).
