# ADR-0005: Accounting Imports Run as Asynchronous Jobs on Dedicated Workers

| | |
|---|---|
| **Status** | Proposed — replaces "in-process background imports" (v1 §5.2, Revision 1) |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0007](0007-resilience.md), [ADR-0010](0010-import-recovery-and-idempotency.md), [ADR-0025](0025-financial-data-pipeline.md) |

## Context

Imports from bexio are long-running (pagination, rate limits) and depend on an unreliable external API. They must not slow interactive requests, and a crash must never leave partial data.

## Decision

- The import API is asynchronous: `POST /v1/import-jobs` → `202 Accepted` + `Location`; `GET /v1/import-jobs/{id}` → status, progress, error. The web app polls until a terminal state.
- Jobs are executed by a **separate worker deployment** of the Accounting service (same image, different process). The API process never runs imports.
- Workers **lease** jobs from the Accounting database (`FOR UPDATE SKIP LOCKED`, `locked_until`, heartbeat), so any number of workers can run safely ([ADR-0010](0010-import-recovery-and-idempotency.md)).
- Job states: `PENDING → RUNNING → COMPLETED | FAILED`. A retry creates a new job.
- On success, the worker writes the ImportBatch and the `accounting.import.completed` outbox event in **one** transaction. Financial Intelligence continues the pipeline asynchronously.
- Per-organization quotas (e.g. one active job per connection, a maximum number of jobs per hour) prevent import storms.

## Alternatives considered

| Option | Why not |
|---|---|
| Imports inside the HTTP request | Timeouts; holds resources; poor user experience |
| A broker-based task queue (Celery etc.) | The database lease is simpler and keeps job state queryable and auditable next to the data |
| WebSockets for progress | Polling is sufficient for minute-scale jobs |

## Consequences

**Positive**: interactive latency is isolated from imports; workers scale independently; job state is transparent.
**Negative**: polling traffic; a lease and heartbeat mechanism to maintain.

## Compliance

- Integration test: start → poll → COMPLETED → `import.completed` published exactly once.
- Test: two workers never execute the same job.
- Load test: imports running in parallel do not raise API p95 latency beyond the alert threshold.

## Revisit when

Job volume makes database polling a bottleneck (move job dispatch to the broker).
