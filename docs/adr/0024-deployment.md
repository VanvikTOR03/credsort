# ADR-0024: Deployment — Docker Compose for Development and Demos; Managed Kubernetes in Switzerland/EU for the Pilot

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0001](0001-architecture-style.md), [ADR-0004](0004-database-per-service.md), [ADR-0016](0016-authentication.md), [09](../architecture/09-deployment-and-operations.md) |

## Context

- Definition of done: a third person can run CredSort from the README and complete the SME-to-lender workflow.
- Demos must survive bexio or LLM outages and run without internet.
- Real SME financials (pilot) fall under the Swiss nFADP; lenders will ask where data is stored.
- The trust zones of [08](../architecture/08-security-and-data-protection.md) must be enforceable by the platform.

## Decision

**Development, CI and demos: Docker Compose**
- All services, workers, the web app, the edge gateway, Keycloak, RabbitMQ and PostgreSQL (one database and role per service) run in Compose.
- Profiles: `offline` (synthetic data, template AI, stub KYB, no network needed), `live` (bexio sandbox, LLM API), `observability`.
- A deterministic seed: 3 synthetic SMEs, 3 lenders, demo users per role, a `DRAFT` price book. The UI header shows OFFLINE or LIVE.

**Pilot: managed Kubernetes in a Swiss or EU region**
- Namespaces per trust zone; **NetworkPolicies** enforce allowed paths; **mTLS** between workloads; per-service egress allowlists.
- Managed PostgreSQL with point-in-time recovery; separate instances for Accounting, Intelligence and Marketplace.
- RabbitMQ cluster (3 nodes, quorum queues); Keycloak and Identity with ≥ 3 replicas.
- Secrets in a secret manager + KMS; infrastructure as code.
- Pilot checklist: region confirmed, DPAs with all processors, backups and restore tested, MFA for all users, fault-injection suite passed.

**CI/CD:** one pipeline per service (path-filtered), contract tests as deploy gates, a Compose-based end-to-end stage, signed images, expand → migrate → contract database migrations.

## Alternatives considered

| Option | Why not |
|---|---|
| Kubernetes for local development | Heavier than needed; Compose reproduces the topology well enough |
| Serverless | Long imports and strict transactions fit poorly; no offline demo |
| VMs without orchestration in the pilot | Network segmentation, mTLS and rolling deploys become manual |

## Consequences

**Positive**: reproducible offline demos; enforceable security zones in the pilot; independent deployments.
**Negative**: a large local stack; pilot hosting cost and platform operations.

## Compliance

- CI: fresh clone + `docker compose --profile offline up` + seed → login works; the offline end-to-end suite runs with backend network egress disabled.
- Pilot: NetworkPolicy tests (FF-C4) and the checklist above.

## Revisit when

Pilot preparation starts (confirm provider and region); or load requires autoscaling policies.
