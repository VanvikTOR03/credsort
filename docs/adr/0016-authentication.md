# ADR-0016: Authentication — Keycloak (OIDC + MFA) with Tokens Kept in the BFF

| | |
|---|---|
| **Status** | Proposed — replaces Revision 1 (built-in sessions for the MVP) |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0018](0018-web-app-and-bff.md), [ADR-0027](0027-context-tokens-and-service-trust.md), [08](../architecture/08-security-and-data-protection.md) |

## Context

Confidentiality is the top characteristic. Revision 1 deferred a real identity provider because of team capacity, which is no longer a constraint. The demo must still run offline.

## Decision

1. **Keycloak** is the identity provider: OIDC authorization code + PKCE, password policy, brute-force detection, **MFA (TOTP/WebAuthn) required** for lender users and SME admins from day one (all users before the pilot).
2. Keycloak runs **inside** the Docker Compose stack, with a realm export of demo users, so offline demos work.
3. The **web app's BFF** is the OIDC client. Access and refresh tokens are stored **server-side** in the BFF's session store. The browser only receives an `HttpOnly`, `Secure`, `SameSite=Lax` session cookie.
4. CSRF protection for state-changing requests to the BFF; a strict Content-Security-Policy.
5. Domain services **do not accept Keycloak user tokens** directly. They accept Identity-issued **context tokens** ([ADR-0027](0027-context-tokens-and-service-trust.md)).
6. Service identities use Keycloak **client credentials** with audience-restricted tokens.
7. Lenders' corporate SSO (identity brokering) is possible later through Keycloak without changes to services.

## Alternatives considered

| Option | Why not |
|---|---|
| Built-in password auth in a service | Reinvents security-critical functionality; no MFA or SSO path |
| Managed SaaS IdP | Breaks offline demos; data-residency review needed; Keycloak can be hosted in the chosen region |
| Tokens in browser storage | XSS exposure |

## Consequences

**Positive**: MFA and SSO-ready from the start; tokens never exposed to the browser.
**Negative**: Keycloak is critical infrastructure to operate (HA in the pilot; realm configuration as code).

## Compliance

- E2E: no tokens in `localStorage`/`sessionStorage`; session cookie flags; CSRF rejection; MFA enforced for the required roles.
- Realm configuration is versioned in `deploy/keycloak/`.

## Revisit when

A lender requires federation with its own IdP (configure brokering); or Keycloak's operating cost outweighs a managed IdP in the pilot region.

## Addendum (2026-11-24): local passwords until Keycloak is connected

Keycloak cannot be run in the development and demo environment, so Identity also supports **local email and password sign-in** for companies, lenders and accountants (`POST /v1/auth/login`, password set at sign-up).

- **Storage:** salted `scrypt` hashes in an Identity-only `credentials` table (row-level security: readable only by the Identity service acting as the platform). Passwords are never logged, put in events, or returned.
- **Rules:** at least 10 characters; 5 failed attempts lock the account for 15 minutes; an unknown email and a wrong password get the same answer and take equally long.
- **No takeover:** registering with a password for an email that already has a user is refused (`email_taken`).
- **Demo accounts** (seeded, synthetic) have no password and sign in with one click from the Demo page. The Demo page and the dev session minting exist only when `AUTH_MODE=dev` and are refused in production.
- **Production** still signs in through Keycloak (this addendum does not replace it): the BFF then refuses password sign-in. Password reset and multi-factor login are not part of this addendum.
