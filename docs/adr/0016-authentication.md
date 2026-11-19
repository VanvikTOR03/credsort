# ADR-0016: Authentication — Built-In Sessions for the MVP, OIDC + MFA Before the Pilot

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0017](0017-tenant-isolation.md), [ADR-0018](0018-single-nextjs-app-with-portals.md), [ADR-0024](0024-deployment-and-demo-modes.md) |

## Context

The plans describe authorization (memberships, consent) but not **authentication**. Constraints:

- Confidentiality is the top characteristic.
- The demo must work **offline** ([ADR-0024](0024-deployment-and-demo-modes.md)).
- The MVP uses synthetic data only; real users and real data come at the pilot.
- Authorization must stay server-side in `access`, not in the frontend.

## Decision

**MVP**
- Authentication lives in the `access` module, using a **maintained library** rather than hand-rolled crypto. Passwords are hashed with **argon2id**.
- **Server-side sessions** referenced by an `HttpOnly`, `Secure`, `SameSite=Lax` cookie. **No tokens in `localStorage`.**
- **CSRF protection** for state-changing requests (double-submit token or same-site plus origin checks).
- Login rate limiting and generic error messages.
- Seeded demo users per organization and role (passwords in the local `.env` only, never committed).
- A request context `(user_id, organization_id, role)` is resolved per request and passed to every use case.

**Before the pilot (mandatory)**
- Move to an **OIDC identity provider with MFA**, hosted in Switzerland or the EU. `access` keeps authorization; only authentication moves.

## Alternatives considered

| Option | Why not now |
|---|---|
| Managed IdP (Auth0, Clerk, etc.) from day one | Breaks the offline demo; an extra vendor; data-residency questions before we need them. |
| Self-hosted Keycloak container | An extra heavy container and configuration for a two-person MVP. |
| NextAuth / auth in the frontend | Splits identity between two runtimes; authorization must be enforced in the backend anyway. |
| JWT in `localStorage` | XSS exposure; revocation is hard. |

## Consequences

**Positive**: works offline; simple; secure defaults for a demo.
**Negative**: no MFA and no SSO in the MVP; migration work before the pilot.

## Compliance

- Tests: unauthenticated requests → 401; session cookie flags set; CSRF-protected mutations reject missing tokens; login rate limit triggers.
- Secrets scanner in CI; `.env` is in `.gitignore`.

## Revisit when

Pilot preparation starts (switch to OIDC + MFA); or a lender requires SSO with its own identity provider.
