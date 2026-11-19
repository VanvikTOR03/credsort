# ADR-0006: API Contracts — Per-Service OpenAPI, External vs Internal APIs, Contract Tests

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0023](0023-event-driven-integration.md), [ADR-0027](0027-context-tokens-and-service-trust.md), [ADR-0015](0015-money-and-financial-calculations.md), [ADR-0030](0030-repository-and-shared-libraries.md) |

## Context

Services are developed and deployed independently. Contracts must be explicit, versioned and verified, or independent deployment becomes lockstep deployment. Some APIs serve the web app (on behalf of users), others serve other services.

## Decision

- **Resource-oriented HTTP/JSON** per service. We do not claim full REST/HATEOAS.
- Every service publishes **one OpenAPI document** in `contracts/openapi/<service>.json`, generated from code and committed.
- Two API surfaces per service:
  - **External** `/v1/*`: called by the BFF on behalf of a user (context token required).
  - **Internal** `/internal/v1/*`: called only by allowed services (service identity token required, plus the user's context token when acting on a user's behalf). Never routable from the edge.
- **Errors:** RFC 9457 `application/problem+json`. For other tenants' resources, 404 rather than 403.
- **Money and ratios** are decimal **strings** ([ADR-0015](0015-money-and-financial-calculations.md)).
- **Idempotency:** mutating external endpoints accept `Idempotency-Key`, stored per (organization, key) for 24 h.
- **Sensitive responses:** `Cache-Control: no-store`.
- **Versioning:** additive changes only within `v1`; breaking changes introduce `v2` alongside `v1` until all consumers migrate.
- **Consumer-driven contract tests:** each consumer publishes its expectations of each provider. The provider's pipeline verifies them before deploying.
- The BFF's TypeScript clients are generated from the OpenAPI documents.

## Alternatives considered

| Option | Why not |
|---|---|
| GraphQL federation | Field-level authorization and consent filtering become much harder exactly where we need them most |
| gRPC internally | No benefit at our call volume; JSON keeps contracts readable for review |
| One API surface per service | Internal capabilities (ledger extracts) would be reachable by users |

## Consequences

**Positive**: independent deployment with confidence; reviewable contracts; typed clients.
**Negative**: contract governance effort; parallel versions during migrations.

## Compliance

- FF-E3: consumer-driven contract tests gate every deployment.
- CI fails if the committed OpenAPI differs from the generated one, or if generated clients are stale.
- FF-C4: internal routes are not reachable through the edge.

## Revisit when

Third parties (lenders' systems) integrate directly → publish a partner API with its own versioning and deprecation policy.
