# ADR-0005: Synchronous Use Cases, In-Process Background Imports with Polling

| | |
|---|---|
| **Status** | Proposed — formalizes Architecture Plan v1 §2.2 and §5.2 |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0007](0007-external-api-resilience.md), [ADR-0010](0010-import-recovery-and-idempotency.md), [ADR-0023](0023-in-process-domain-events.md) |

## Context

Most operations are short (create an application, submit an offer, select an offer). Importing from bexio can take long (pagination, rate limits). We want no broker or extra infrastructure ([ADR-0001](0001-modular-monolith.md)).

## Decision

- Short use cases are **synchronous** HTTP requests with in-process module calls.
- Imports are **asynchronous jobs** run by an in-process background runner:
  - `POST /api/companies/{id}/import-jobs` → `202 Accepted` with `Location: /api/import-jobs/{job_id}`.
  - `GET /api/import-jobs/{job_id}` → status, progress, error, links to results.
  - The frontend polls at a modest interval (e.g. every 2–5 s) and stops at a terminal state.
- Job states: `PENDING → RUNNING → COMPLETED | FAILED` ([ADR-0010](0010-import-recovery-and-idempotency.md)).
- The runner is a small loop that claims `PENDING` jobs from the database (`FOR UPDATE SKIP LOCKED`). The same code can later run as a separate `worker` process from the same image without design changes.

## Alternatives considered

| Option | Why not |
|---|---|
| Celery/RQ + Redis or RabbitMQ | Extra infrastructure and failure modes for a handful of imports. |
| Synchronous import inside the HTTP request | Timeouts; a poor user experience; a held DB connection. |
| WebSockets / server-sent events for progress | More moving parts; polling is enough at this scale. |

## Consequences

**Positive**: no extra infrastructure; jobs are visible in the DB; easy to test.
**Negative**: jobs are interrupted when the process restarts (handled by [ADR-0010](0010-import-recovery-and-idempotency.md)); long imports share CPU with requests.

## Compliance

- Integration test: start an import, poll until COMPLETED, verify snapshot creation.
- Test: two runners never process the same job (claiming uses row locks).

## Revisit when

Import duration or concurrency measurably degrades interactive latency → run the `worker` process; if that is not enough, consider a queue.
