# ADR-0029: Observability — OpenTelemetry Across HTTP and Messages, Without Sensitive Data

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0023](0023-event-driven-integration.md), [ADR-0011](0011-consistency-model.md), [09 §6](../architecture/09-deployment-and-operations.md) |

## Context

A user journey crosses the BFF, several services, the broker and workers. Without end-to-end visibility, failures in a distributed system are slow to find. Telemetry must not become a leak of confidential data.

## Decision

1. **OpenTelemetry** SDKs in the web app and every service, exporting traces, metrics and logs to a collector.
2. **Trace context propagation** over HTTP (`traceparent`) and through events (CloudEvents `traceparent` extension), so a selection can be followed into Billing and Notification.
3. **Structured logs** with an **allowlist** of fields (IDs, states, versions, durations, error codes). Request and response bodies are never logged or recorded as span attributes.
4. **Golden signals** per service plus architecture-specific metrics: outbox lag, DLQ depth, inbox duplicates, reconciliation mismatches, circuit-breaker state, import durations, quote failures, context-token issuance errors.
5. Alerts as listed in [09 §6](../architecture/09-deployment-and-operations.md).
6. Locally, the observability stack is an optional Compose profile; in the pilot, a managed backend in the same region.

## Alternatives considered

| Option | Why not |
|---|---|
| Logs only | No causal view across services and messages |
| Vendor-specific agents | Lock-in; OpenTelemetry keeps the backend replaceable |
| Full request/response logging | Confidentiality violation |

## Consequences

**Positive**: fast diagnosis of distributed failures; operational metrics for the consistency model.
**Negative**: instrumentation effort; telemetry storage cost.

## Compliance

FF-C6 (sentinel values never appear in logs or spans), FF-F3 (trace context present on requests and messages), alert rules versioned with deployment configuration.

## Revisit when

Telemetry volume or cost requires sampling strategies beyond head sampling.
