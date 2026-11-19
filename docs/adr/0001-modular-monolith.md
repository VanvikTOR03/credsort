# ADR-0001: Domain-Partitioned Modular Monolith as the Architecture Style

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team (Developer A, Developer B) |
| **Owner** | To assign |
| **Related** | [ADR-0012](0012-driving-architecture-characteristics.md), [ADR-0002](0002-six-domain-modules.md), [05-architecture-style.md](../architecture/05-architecture-style.md) |

## Context

- Driving characteristics are **confidentiality, data integrity and evolvability**; **feasibility** (two developers, AI-assisted, course deadlines) is a hard constraint.
- Core use cases need **local ACID transactions**: selecting an offer, recording the fee and writing the audit event must succeed or fail together.
- Volume is small (tens of SMEs and lenders in the MVP), and the demo must also run **offline**.
- The business model is still changing (SMEs are now charged; amounts TBD), so module boundaries must make change local.

## Decision

We will build CredSort as a **domain-partitioned modular monolith with ports & adapters at the external edges**:

- One FastAPI backend process containing six domain modules ([ADR-0002](0002-six-domain-modules.md)).
- One PostgreSQL database with a schema per module ([ADR-0004](0004-single-postgresql-and-table-ownership.md)).
- One Next.js frontend ([ADR-0018](0018-single-nextjs-app-with-portals.md)).
- One deployment unit via Docker Compose; **one architecture quantum**.
- **No** microservices, message broker, Redis, Kubernetes, GraphQL, API gateway or service mesh without a demonstrated, measured need.

## Alternatives considered

Weighted scoring in [05-architecture-style.md §3](../architecture/05-architecture-style.md): modular monolith 56/65, microkernel 46, service-based 45, layered 44, microservices 33, event-driven 32, space-based 25.

| Option | Why not |
|---|---|
| Layered monolith | Technical partitioning spreads every business change over all layers and blurs consent, scoring and billing. |
| Microservices | Distributed transactions for selection + fee + audit; a larger attack surface; operations beyond a two-person team. |
| Event-driven | Eventual consistency conflicts with "exactly one selected offer"; harder to debug and to reproduce demos. |
| Service-based | The most credible later step; premature today (network, service auth, deployment overhead without benefit). |
| Microkernel | Adopted partially: providers are plug-ins behind ports. The core is a multi-domain workflow, not one core with plug-ins. |

## Consequences

**Positive**
- Simple local development and deployment (`docker compose up`).
- ACID guarantees across modules; DB constraints protect invariants.
- One security perimeter; authorization is centralized and consistently enforced.
- Modules are extractable later because they communicate through `api.py` and own their data.

**Negative / trade-offs**
- No independent deployment or scaling per module.
- A crash in one module can take down the whole backend.
- Module boundaries live in code and can erode without automated checks.

## Compliance

- import-linter contracts in CI ([05 §7](../architecture/05-architecture-style.md)).
- `docker-compose.yml` contains only `frontend`, `backend` and `postgres` (plus, later, an optional `worker` from the same image). Adding a new kind of infrastructure requires a new ADR.

## Revisit when

Sustained import load blocks interactive requests; AI must scale or fail independently; production bank integrations require separate security zones; more than about 6 developers work in parallel; or a regulator requires isolation of a component.
