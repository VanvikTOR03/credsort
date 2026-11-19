# ADR-0001: Service-Based Architecture with Event-Driven Integration, Plug-in Edges and a Financial Data Pipeline

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0012](0012-driving-architecture-characteristics.md), [ADR-0002](0002-service-decomposition.md), [ADR-0023](0023-event-driven-integration.md), [ADR-0025](0025-financial-data-pipeline.md), [05-architecture-style.md](../architecture/05-architecture-style.md), [07-failure-modes-and-risks.md](../architecture/07-failure-modes-and-risks.md) |

## Context

- Driving characteristics: **confidentiality, data integrity, evolvability** ([ADR-0012](0012-driving-architecture-characteristics.md)). Supporting: fault tolerance, auditability, explainability, testability, interoperability.
- Stakeholder direction (2026-11-19): choose the style **purely on these characteristics**. Team size and implementation effort are not constraints.
- The core marketplace invariants must hold atomically: a published application always has a consent record and a frozen profile, there is at most one selected offer, and every critical action is audited.
- External providers (bexio, LLM, KYB, invoicing) are unreliable or replaceable. The revenue model and data sources will keep changing.

**Decision history.** The v1 plan and Revision 1 of this ADR (commit `f45046c`) chose a modular monolith, mainly for feasibility. That constraint was removed, and the decision was re-evaluated.

## Decision

We will build CredSort as a **hybrid**:

1. **Service-based backbone.** Six coarse-grained domain services (Identity, Accounting Integration, Financial Intelligence, Marketplace, Billing, Advisory), each with **its own database**, plus two platform services (Notification, Audit), a web app with a backend-for-frontend (BFF), and an edge gateway ([ADR-0002](0002-service-decomposition.md), [ADR-0004](0004-database-per-service.md)).
2. **Event-driven integration between services.** Transactional outbox → RabbitMQ → idempotent inbox; thin events; claim check for large or sensitive payloads ([ADR-0023](0023-event-driven-integration.md)).
3. **Transactional core kept whole.** Applications, consent, published profiles, matching, offers, selection and their audit live in **one** service (Marketplace), so the critical invariants are local ACID transactions ([ADR-0011](0011-consistency-model.md)).
4. **Microkernel-style plug-ins at every external edge** and for versioned rule sets: accounting sources, LLMs, KYB, invoicing, fee calculators, mappings, scorecards ([ADR-0003](0003-plug-in-extension-points.md)).
5. **Pipes-and-filters pipeline** from imported ledger to assessment, with versioned, pure, reproducible steps ([ADR-0025](0025-financial-data-pipeline.md)).
6. **Strict runtime rules:** synchronous calls only from downstream to upstream services, never in cycles, at most two hops per request, never inside a database transaction; the complete list of allowed synchronous calls is fixed in [06 §2](../architecture/06-runtime-and-integration.md).

## Alternatives considered

Weighted scoring in [05 §3](../architecture/05-architecture-style.md) (max 60): **chosen hybrid 55**, modular monolith + microkernel + pipeline 49, service-based with DB per service 48, modular monolith 43, service-based with shared DB 41, microservices + event-driven 39, microservices 38, event-driven 36, orchestration SOA 33, serverless 33, layered 31, space-based 29.

| Option | Why not |
|---|---|
| Modular monolith (± plug-ins and pipeline) | Strongest integrity, but every module can reach all data and one failure stops everything: weaker confidentiality isolation and fault tolerance |
| Service-based with a shared database | The shared database is a shared blast radius and a coupling point |
| Microservices | Splits the consent → matching → offer → selection flow into sagas (integrity loss), copies financial data into many services (confidentiality loss); its strength, fine-grained scaling, is not a need |
| Pure event-driven | Eventual consistency everywhere conflicts with "exactly one selected offer" and auditable, reproducible results |
| Space-based, orchestration SOA, serverless | Built for needs CredSort does not have, or weak on integrity and evolvability |

## Consequences

**Positive**
- Data isolation and least privilege per service; Advisory and Notification never touch financial databases.
- Failures of bexio, the LLM, Billing or Notification are contained.
- Pricing, integrations and AI evolve and deploy independently.
- Assessments are reproducible and explainable; the activity history is complete and tamper-evident.

**Negative / trade-offs**
- Cross-service effects (fees, snapshots, audit, notifications) are **eventually** consistent. They are guaranteed by outbox, inbox and reconciliation, but they can lag.
- More infrastructure: Keycloak, RabbitMQ, a gateway, several databases, observability.
- Identity is a shared critical runtime dependency (accepted; engineered for high availability).
- Restoring one service's database requires a replay-and-reconcile runbook.

All break points and design responses are catalogued in [07](../architecture/07-failure-modes-and-risks.md).

## Compliance

- FF-E6: static check of declared service clients → no cycles, no path longer than two hops, only the calls listed in [06 §2](../architecture/06-runtime-and-integration.md).
- FF-E5: every service builds, tests and deploys alone.
- FF-C4: databases and internal APIs are unreachable from the edge and from non-allowed services.
- Any new service, new synchronous dependency or new infrastructure component requires a new ADR.

## Revisit when

A single service becomes a hotspot needing finer decomposition; identity outages measurably hurt availability; event volume or replay needs outgrow RabbitMQ; or a regulator requires isolating a component (e.g. payments) in its own zone.
