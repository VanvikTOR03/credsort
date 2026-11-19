# ADR-0006: Resource-Oriented HTTP/JSON API with a Contract-First OpenAPI

| | |
|---|---|
| **Status** | Proposed — formalizes Architecture Plan v1 §7 |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0018](0018-single-nextjs-app-with-portals.md), [ADR-0015](0015-money-and-financial-calculations.md) |

## Context

Two developers (and AI coding assistants) will build the frontend and backend in parallel. They need an agreed contract before generating code. The API carries confidential data.

## Decision

- **Resource-oriented HTTP/JSON.** We do not claim full REST/HATEOAS compliance.
- **Contract first:** endpoints, request/response Pydantic models and error cases are agreed and merged *before* implementation. FastAPI generates `docs/api/openapi.json`, which is **committed**. The frontend client is **generated** from it.
- **Errors:** RFC 9457 `application/problem+json`, with 401 / 403 / 404 / 409 / 422 semantics defined per endpoint. For other tenants' resources, 404 is preferred over 403 so existence is not disclosed.
- **Sensitive responses:** `Cache-Control: no-store`.
- **Money and ratios** are serialized as **decimal strings**, never JSON floats ([ADR-0015](0015-money-and-financial-calculations.md)).
- **Idempotency:** retried mutations (publish, submit offer, select offer) accept an `Idempotency-Key` header.
- **Versioning:** a single unversioned `/api` during the MVP; breaking changes go through PR review and client regeneration.
- The endpoint list in Architecture Plan v1 §7.1 is the starting point, plus `billing` endpoints such as `GET /api/companies/{id}/fee-quote?trigger=…` and `GET /api/companies/{id}/charges`.

## Alternatives considered

| Option | Why not |
|---|---|
| GraphQL | Field-level authorization becomes harder exactly where we need it most (consented fields); extra tooling. |
| Hand-written frontend types | They drift from the backend; error-prone with generated code. |

## Consequences

**Positive**: parallel work; typed client; the contract is reviewable in PRs.
**Negative**: schema changes require regeneration and review discipline.

## Compliance

- CI fails if the generated `openapi.json` differs from the committed file.
- CI fails if the frontend client is stale relative to `openapi.json`.
- A test asserts that every authenticated response includes `Cache-Control: no-store`.

## Revisit when

Third parties (lenders' systems) consume the API → introduce an explicit `/v1` and a deprecation policy.
