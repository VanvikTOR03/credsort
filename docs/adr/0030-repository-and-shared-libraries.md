# ADR-0030: Monorepo, Contracts Folder, Technical-Only Shared Libraries, Independent Pipelines

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0002](0002-service-decomposition.md), [ADR-0006](0006-api-contracts.md), [ADR-0023](0023-event-driven-integration.md), [ADR-0024](0024-deployment.md) |

## Context

Services must evolve and deploy independently (evolvability), while contracts must be visible and reviewable in one place. Shared code is useful for technical concerns (outbox, auth verification, money type) but becomes hidden coupling if it contains business rules.

## Decision

**One Git repository (monorepo)** with this layout:

```text
credsort/
  services/
    identity/  accounting/  intelligence/  marketplace/  billing/  advisory/  notification/  audit/
      app/            # api/ (external + internal routes), application/, domain/, plugins/, persistence/
      migrations/     # owned by this service only
      tests/          # unit, integration, contract
      Dockerfile
  web/                # Next.js app + BFF
  libs/
    credsort-common/  # technical only: event envelope, outbox relay, inbox, token verification,
                      # resilient HTTP client, Money/Decimal, problem+json, OpenTelemetry setup
  contracts/
    openapi/<service>.json
    events/<service>/<event>.v<major>.schema.json
  deploy/
    compose/  keycloak/  rabbitmq/  infra/   # infra = pilot infrastructure as code
  demo_data/
  docs/
```

Rules:
1. **Services never import each other's code.** Communication only via contracts (APIs, events).
2. `libs/credsort-common` contains **no domain logic** (no fees, scoring, consent rules) and is **versioned**; services pin a version and upgrade independently.
3. `contracts/` is the single place for API and event schemas; changes there require review by the owning service and its consumers.
4. **One CI/CD pipeline per service** (path filters), plus a system pipeline for end-to-end tests.
5. All backend services use Python + FastAPI; the web app uses TypeScript + Next.js. A service may only change language with a new ADR.

## Alternatives considered

| Option | Why not |
|---|---|
| One repository per service | Contracts and cross-cutting reviews spread across repositories; harder end-to-end testing |
| A shared "domain" library | Hidden coupling; one change forces coordinated releases |
| No shared library at all | Each service re-implements outbox, auth and money handling, so integrity and security bugs multiply |

## Consequences

**Positive**: independent services with visible contracts; consistent technical foundations.
**Negative**: monorepo tooling (path-filtered pipelines); discipline to keep the shared library technical.

## Compliance

FF-E5 (each service builds and deploys alone), FF-E7 (no domain logic in libs; import rules forbid `services/*` importing other `services/*`).

## Revisit when

Independent teams own services with conflicting release processes (consider splitting repositories).
