# ADR-0007: Resilience — Timeouts, Retries, Circuit Breakers, Bulkheads and Fallbacks

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0003](0003-plug-in-extension-points.md), [ADR-0011](0011-consistency-model.md), [06 §2](../architecture/06-runtime-and-integration.md), [07 §3](../architecture/07-failure-modes-and-risks.md) |

## Context

With several services and external providers, partial failure is normal. Failures must stay contained, must never corrupt data, and must produce clear user-facing behaviour.

## Decision

**Every remote call** (internal or external):
- has an explicit **timeout** (values in [06 §2](../architecture/06-runtime-and-integration.md); external defaults: bexio 5 s connect / 30 s read, LLM 15 s);
- is **retried only if idempotent** (GET, or a POST with an idempotency key), at most 3 attempts with exponential backoff and jitter; 429 honours `Retry-After`; **401/403 are never retried**;
- goes through a **circuit breaker** per upstream;
- uses a **separate connection pool per upstream** (bulkhead), so one slow dependency cannot exhaust the service;
- is made **outside** database transactions.

**Defined fallbacks**

| Failure | Behaviour |
|---|---|
| bexio | Job FAILED with a reason; the last validated snapshot stays current |
| LLM | Template plug-in explanation, labelled as such |
| Billing (quotes) | Use a valid cached quote; otherwise the fee-bearing action is **blocked** (fail closed) |
| Intelligence (profile extract) | Publication blocked with a clear message; matching and offers continue |
| Broker | Events wait in outboxes; synchronous journeys continue |
| Identity | Existing context tokens work until expiry; new logins fail |

## Alternatives considered

| Option | Why not |
|---|---|
| Unbounded retries | Amplify outages; hide authorization errors |
| Fail open on Billing (charge later) | Would charge fees that were never shown, violating integrity and transparency |
| A service mesh for resilience policies | Policies live in the shared client library instead; a mesh may still provide mTLS in the pilot ([ADR-0024](0024-deployment.md)) |

## Consequences

**Positive**: predictable, contained failures; no partial data.
**Negative**: tuning effort; fail-closed paths reduce availability by design.

## Compliance

- FF-F1 fault-injection suite ([07 §8](../architecture/07-failure-modes-and-risks.md)).
- Static check: every HTTP client is created through the shared resilient client (timeouts mandatory).

## Revisit when

Real traffic shows timeouts or retries mis-tuned; or a provider offers webhooks that remove polling.
