# ADR-0024: Docker Compose Deployment, Offline/Live Demo Modes, Swiss/EU Hosting for the Pilot

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0001](0001-modular-monolith.md), [ADR-0003](0003-ports-and-adapters.md), [ADR-0016](0016-authentication.md), [ADR-0017](0017-tenant-isolation.md) |

## Context

- Definition of done: "a third person can run CredSort using the instructions and complete the SME-to-lender workflow."
- The demo must survive bexio or LLM outages and work without internet.
- Real SME financials (pilot) fall under the Swiss Federal Act on Data Protection (nFADP), and lenders will ask where data is stored.

## Decision

**MVP**
1. **Docker Compose** with three services: `frontend`, `backend`, `postgres` (an optional `worker` from the backend image later, [ADR-0005](0005-sync-use-cases-and-background-import.md)).
2. Configuration via environment variables; `.env.example` committed, `.env` never committed.
3. **Two demo modes**, selected by configuration and shown in the UI header:
   - **OFFLINE**: `SyntheticDataAdapter`, `TemplateAdapter`, `StubKybAdapter`; no network needed.
   - **LIVE**: `BexioAdapter` (sandbox) and `LlmApiAdapter`; the UI clearly marks what is real and what is simulated.
4. A **deterministic seed**: 3 synthetic SMEs with different risk profiles, 3 simulated lenders, demo users per role, a `DRAFT` price book ([ADR-0013](0013-billing-and-sme-charging.md)).
5. **CI on GitHub Actions**: lint, type checks, unit/integration tests, architecture tests, OpenAPI drift check, Playwright end-to-end tests on the compose stack.

**Pilot (before real data)**
6. Managed PostgreSQL and app hosting in a **Swiss or EU region**, with encryption at rest, automated backups and tested restore.
7. RLS enabled ([ADR-0017](0017-tenant-isolation.md)), OIDC + MFA ([ADR-0016](0016-authentication.md)), secrets in a secret manager, and a data-processing review of every external provider (LLM, KYB, invoicing).

## Alternatives considered

| Option | Why not |
|---|---|
| Kubernetes | Far beyond the needs and capacity of the team. |
| Serverless functions | Long-running imports and an in-process job runner fit poorly; harder offline demos. |
| Cloud hosting from day one | Not needed for a synthetic-data MVP; the offline demo is the safer presentation path. |

## Consequences

**Positive**: reproducible demos; a resilient presentation; a clear pilot hardening list.
**Negative**: the pilot needs a hosting project (cost, setup) and a data-protection review.

## Compliance

- A fresh clone + `docker compose up` + seed reaches a working login (tested in CI).
- The OFFLINE mode end-to-end test runs with network access disabled for the backend.
- Pilot checklist: hosting region, backups/restore test, RLS, MFA, secrets manager, provider reviews.

## Revisit when

Pilot preparation starts; or availability or scaling requirements appear ([ADR-0012](0012-driving-architecture-characteristics.md)).
