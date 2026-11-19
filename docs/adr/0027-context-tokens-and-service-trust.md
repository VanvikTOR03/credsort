# ADR-0027: Context Tokens and Service-to-Service Trust

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | Identity owner |
| **Related** | [ADR-0016](0016-authentication.md), [ADR-0017](0017-tenant-isolation.md), [ADR-0019](0019-organization-types-and-delegation.md), [ADR-0020](0020-kyb-outsourced-via-port.md), [08](../architecture/08-security-and-data-protection.md) |

## Context

Every service must authorize every request (zero trust) without calling Identity each time. A Keycloak token says *who* the user is, but not *which organization* they act for, their role there, their delegations, or the organization's KYB status. Internal APIs must also know *which service* is calling.

## Decision

**User context**
1. The BFF exchanges the user's Keycloak token plus the selected organization for an Identity-issued **context token** (`POST /v1/context-tokens`).
2. Identity verifies membership, role, delegation, organization status and KYB status, and returns a signed JWS with claims: `sub` (user), `org_id`, `org_type`, `role`, `scopes`, `on_behalf_of` (delegation, if any), `kyb_status`, `jti`, `iat`, `exp`, `aud = credsort-services`.
3. **Lifetime about 2 minutes**; the BFF caches and refreshes it.
4. Services verify the signature (cached JWKS), audience, expiry and the **deny-list**. Services accept **only** context tokens for user calls; Keycloak user tokens are rejected.
5. **Deny-list:** services consume `identity.membership.revoked` and `identity.organization.suspended` and reject tokens for those subjects issued before the revocation time, until those tokens expire.
6. Signing keys rotate with a JWKS overlap of ≥ 24 h.

**Service identity**
7. Each service has a Keycloak client; internal calls carry an audience-restricted **service token** (client credentials). When acting for a user, the caller also forwards the user's context token.
8. Each internal endpoint has an **allowed-callers list** (e.g. `profile-extract` only from Marketplace; `advisory-context` only from Advisory; `ledger` only from Intelligence).
9. In the pilot, **mTLS** between workloads adds transport-level identity; NetworkPolicies restrict paths ([ADR-0024](0024-deployment.md)).
10. Tokens are never logged; only `jti` may appear in logs.

## Alternatives considered

| Option | Why not |
|---|---|
| Services call Identity on every request | Latency and a hard runtime dependency on every call |
| Put organization data into Keycloak tokens | Membership, delegation and KYB live in our domain; syncing them into Keycloak duplicates the source of truth |
| Long-lived tokens | Large revocation window |
| Trust the internal network | One compromised component could call everything |

## Consequences

**Positive**: zero-trust authorization at every hop; revocation within seconds (worst case about 2 minutes); least privilege for service calls.
**Negative**: Identity becomes a critical runtime dependency (HA required); key rotation and deny-lists must be operated correctly ([07](../architecture/07-failure-modes-and-risks.md) R-A1, R-A10, R-C3).

## Compliance

- Tests: expired, wrong-audience, tampered and deny-listed tokens are rejected by every service; internal endpoints reject callers not on their allowed list; a Keycloak user token is rejected by domain services.
- FF-C4 network tests in the pilot.

## Revisit when

Revocation must be instantaneous (consider token introspection for high-risk actions); or lenders federate their own IdPs.
