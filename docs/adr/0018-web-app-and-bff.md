# ADR-0018: One Next.js Web App as Backend-for-Frontend; Portals as Route Groups

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0006](0006-api-contracts.md), [ADR-0016](0016-authentication.md), [ADR-0027](0027-context-tokens-and-service-trust.md), [02](../architecture/02-use-case-and-screens.md) |

## Context

CredSort has SME and lender portals (P0), an admin area and later a fiduciary portal. With several services behind it, the browser must not call services directly (token exposure, CORS, many origins).

## Decision

1. **One Next.js (App Router, TypeScript) application** with route groups `(sme)`, `(lender)`, `(admin)` and later `(fiduciary)`, with role-based navigation.
2. Its **server side is the BFF**: it is the OIDC client, keeps tokens in a server-side session store, obtains **context tokens** from Identity per selected organization, and calls services' **external** APIs.
3. The browser talks **only** to the web app (same origin); services are not reachable from the browser.
4. The BFF composes data for screens (e.g. the comparison page from Marketplace + Billing quotes) but contains **no business rules**: no financial calculations, no authorization decisions. Services enforce everything.
5. API clients are generated from the services' OpenAPI documents ([ADR-0006](0006-api-contracts.md)); decimals arrive as strings and are only formatted.
6. The session store is a small dedicated database owned by the web app.

## Alternatives considered

| Option | Why not |
|---|---|
| Browser calls services directly | Tokens in the browser; CORS for many origins; every service exposed |
| Separate apps per portal | Duplicated auth, components and pipelines |
| GraphQL gateway as BFF | Field-level consent filtering belongs in Marketplace, not in a gateway |

## Consequences

**Positive**: tokens never reach the browser; one origin; screen-specific composition without leaking logic.
**Negative**: the BFF is on every request path (scaled horizontally, stateless apart from the session store).

## Compliance

- E2E: no tokens in browser storage; services unreachable from the browser (FF-C4).
- Review rule: no arithmetic on money values and no authorization logic in the web app.

## Revisit when

A portal needs separate branding or release cadence (e.g. a white-label lender portal).
