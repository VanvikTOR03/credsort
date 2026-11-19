# ADR-0018: One Next.js App with Portals as Route Groups

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | Developer B (frontend) |
| **Related** | [ADR-0006](0006-http-json-api-and-openapi-contract.md), [ADR-0016](0016-authentication.md), [02-use-case-and-screens.md](../architecture/02-use-case-and-screens.md) |

## Context

CredSort has an SME portal and a lender portal (P0), an admin area, and later a fiduciary portal. The plans fix Next.js + TypeScript but not whether these are separate apps, how the browser reaches FastAPI, or where logic may live.

## Decision

1. **One Next.js (App Router, TypeScript) application.** The portals are **route groups**: `app/(sme)`, `app/(lender)`, `app/(admin)`, and later `app/(fiduciary)`, with role-based navigation and layout.
2. The browser calls **same-origin `/api/*`**, which Next.js **rewrites (proxies)** to FastAPI. The session cookie stays first-party; no CORS configuration.
3. **No business logic in the frontend**: no financial calculations, no authorization decisions (the UI may hide buttons, but the backend decides). Server components may call the API, forwarding the user's cookie.
4. The API client is **generated** from `docs/api/openapi.json` ([ADR-0006](0006-http-json-api-and-openapi-contract.md)).
5. Decimal values arrive as strings and are only formatted ([ADR-0015](0015-money-and-financial-calculations.md)).
6. The UI component library is a team choice, not an architectural decision.

## Alternatives considered

| Option | Why not |
|---|---|
| Two separate Next.js apps (SME, lender) | Duplicated auth, components and build pipelines for two developers. |
| Browser calls FastAPI directly (cross-origin) | CORS plus cross-site cookie complexity; weaker CSRF posture. |
| Next.js as a BFF with business logic | Splits domain logic across two runtimes; breaks "one place for rules". |

## Consequences

**Positive**: one build, shared components, simple auth, first-party cookies.
**Negative**: portal code must be kept separated by convention; one deployment for all portals.

## Compliance

- Lint/review rule: no imports from the `(lender)` route group into `(sme)` and vice versa except a shared `components/` folder.
- No arithmetic on money values in the frontend (review rule; search for numeric parsing of decimal fields).

## Revisit when

A portal needs a separate release cadence or branding (e.g. a white-label lender portal).
