# 09 — Deployment and Operations

**Date:** 2026-11-19 · **Status:** Proposed · **Decisions:** [ADR-0024](../adr/0024-deployment.md), [ADR-0029](../adr/0029-observability.md), [ADR-0030](../adr/0030-repository-and-shared-libraries.md)

## 1. Environments

| Environment | Purpose | Platform | Data |
|---|---|---|---|
| **Local** | Development | Docker Compose | Synthetic only |
| **Demo · OFFLINE** | Presentations without internet | Docker Compose, `offline` profile | Synthetic; template AI; stub KYB |
| **Demo · LIVE** | Show real integrations | Docker Compose, `live` profile | bexio sandbox, LLM API; synthetic lenders |
| **CI** | Tests per service and end to end | GitHub Actions + Compose | Synthetic |
| **Pilot** | Real SMEs and lenders | Managed Kubernetes in a Swiss or EU region | Real; only after the pilot checklist is complete |

## 2. Local and demo topology (Docker Compose)

| Container | Notes |
|---|---|
| `edge` | Reverse proxy / gateway (TLS locally via a dev certificate) |
| `web` | Next.js app + BFF |
| `keycloak` | Realm imported from `deploy/keycloak/realm.json` with demo users per role |
| `identity`, `accounting`, `accounting-worker`, `intelligence`, `intelligence-worker`, `marketplace`, `billing`, `advisory`, `notification`, `audit` | One image per service; workers reuse their service's image |
| `postgres` | One container locally, but **one database and one role per service**; each role can connect only to its own database |
| `rabbitmq` | Definitions (exchanges, queues, DLQs) imported at startup |
| `otel-collector` + observability backend | Optional `observability` profile |

`docker compose --profile offline up` starts a complete, network-independent demo. The UI header shows **OFFLINE** or **LIVE**.

## 3. Pilot topology

| Component | Configuration |
|---|---|
| Kubernetes | Managed cluster in Switzerland or the EU; one namespace per zone; **NetworkPolicies** enforce the trust zones of [08](08-security-and-data-protection.md) |
| mTLS | Between all workloads (platform-provided or a lightweight service mesh) |
| Services | ≥ 2 replicas each; Identity and Keycloak ≥ 3 for high availability; workers scaled separately |
| Databases | Managed PostgreSQL; **separate instances** for Accounting, Intelligence and Marketplace (C4/C3 data), others may share an instance with separate databases and roles; point-in-time recovery |
| Broker | RabbitMQ cluster of 3 nodes with quorum queues |
| Edge | Managed load balancer + WAF + gateway |
| Secrets | Secret manager + KMS; no secrets in images or manifests |

## 4. CI/CD

| Stage | Per service | Whole system |
|---|---|---|
| Build | Lint, type check, unit tests, architecture rules | — |
| Contract | OpenAPI and event-schema compatibility checks; consumer-driven contract tests | — |
| Security | Dependency scan, secrets scan, container image scan, image signing | — |
| Integration | Service + its DB + broker in containers | — |
| End to end | — | Compose stack: Playwright journeys, cross-tenant probe suite, indirect-disclosure suite, fault injection |
| Deploy | Independent, path-filtered pipelines; database migrations use **expand → migrate → contract** so old and new versions run side by side | Deploy order is never required between services (backward-compatible contracts) |

## 5. Backups and restore

| Rule | Why |
|---|---|
| Point-in-time recovery for every database; encrypted backups | Integrity and confidentiality |
| Outbox tables retain published events ≥ 35 days | Allows **replaying** events after a restore |
| **Restore procedure** = restore one database → replay outboxes of upstream services since the restore point → run reconciliation jobs → only then reopen traffic | Restoring one service in isolation would otherwise break cross-service consistency (see [07](07-failure-modes-and-risks.md) R-I8) |
| Quarterly restore test per database in the pilot | A backup is only as good as its tested restore |

## 6. Observability and alerts

| Signal | Alert when |
|---|---|
| Outbox lag (oldest unsent event) | > 1 minute |
| DLQ depth | > 0 |
| Reconciliation mismatches | > 0 |
| Import failure rate | > 20 % in 1 hour |
| Context-token issuance errors | Any burst |
| Audit hash-chain verification | Any failure |
| Circuit breaker open (any internal call) | Open > 1 minute |
| p95 latency of publish, select, match | > 2 s |

## 7. Runbooks (to be written before the pilot)

1. Event stuck in DLQ: inspect, fix, replay.
2. Reconciliation mismatch: fees, snapshots, audit.
3. Restore a single service database with outbox replay.
4. Rotate context-token signing keys and bexio encryption keys.
5. Revoke a compromised user or organization immediately.
6. Price-book activation and rollback (activate the previous version as a new one).
7. Provider outage (bexio, LLM, KYB, invoicing).
8. Organization deletion request tracking.
