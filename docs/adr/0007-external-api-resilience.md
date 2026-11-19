# ADR-0007: External API Timeouts, Bounded Retries and Fallbacks

| | |
|---|---|
| **Status** | Proposed — formalizes Architecture Plan v1 §5.2–5.3 |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0003](0003-ports-and-adapters.md), [ADR-0005](0005-sync-use-cases-and-background-import.md), [ADR-0009](0009-ai-explains-deterministic-results.md) |

## Context

bexio and the LLM provider are outside our control. Failures must produce controlled errors, never corrupt data, and never block the synthetic MVP or an offline demo.

## Decision

**bexio (inside import jobs)**
- Explicit connect and read timeouts on every call (starting values: 5 s connect, 30 s read; tuned after the feasibility test).
- Retry **only** 429, 502, 503, 504 and network errors; at most 3 attempts; exponential backoff with jitter; honour `Retry-After`.
- **Never retry 401/403.** Mark the job FAILED with "reconnect bexio / check permissions".
- Keep the **last validated snapshot** visible with its date; a failed import never replaces it.

**LLM (advisory)**
- Request timeout (starting value 15 s) and a maximum input size.
- On timeout, error, or AI disabled → `TemplateAdapter` with deterministic explanations, clearly labelled.

**General**
- All external calls go through adapters; use cases receive typed results or domain errors, never raw HTTP exceptions.
- A circuit breaker is **deferred** until real operational problems justify it.

## Alternatives considered

| Option | Why not |
|---|---|
| Unbounded or naive retries | They hammer the vendor, hit rate limits harder and hide authorization problems. |
| Circuit breaker library now | Extra complexity without observed need. |

## Consequences

**Positive**: predictable failures; the demo survives outages; no partial data.
**Negative**: timeouts and retry counts need tuning against real sandbox behaviour.

## Compliance

- Integration tests with a fake server simulating 429 with `Retry-After`, 503, timeouts and 401.
- A test confirms the previous snapshot stays current after a failed import.
- A test confirms the advisory endpoint returns a template explanation when the LLM adapter times out.

## Revisit when

Repeated provider outages degrade the user experience → add a circuit breaker; or a pilot SLA requires alerting.
