# ADR-0017: Tenant Isolation — Database per Service, Scoped Queries and Row-Level Security from Day One

| | |
|---|---|
| **Status** | Proposed — replaces Revision 1 (RLS deferred to the pilot) |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0004](0004-database-per-service.md), [ADR-0008](0008-consent-and-permitted-field-matching.md), [ADR-0027](0027-context-tokens-and-service-trust.md) |

## Context

All tenants (SMEs, lenders, fiduciaries) share each service's database. A single forgotten tenant filter would expose a company's financials, which is the worst possible failure for CredSort.

## Decision

Three independent layers in every multi-tenant service:

1. **Application layer:** repositories for tenant data require the request's `AccessContext` (from the verified context token) and apply the scope. No unscoped query methods exist for tenant tables; platform-admin access uses a separate, explicitly named and audited path.
2. **Database layer:** **PostgreSQL row-level security** on every tenant table from day one. Each transaction sets `app.org_id` and `app.role` (`SET LOCAL`); policies restrict rows accordingly. The service's DB role cannot bypass RLS (no `BYPASSRLS`, not the table owner).
3. **Verification layer:** the cross-tenant **probe suite** calls every external endpoint with another tenant's IDs and expects 404/403.

Cross-tenant access exists only through explicit mechanisms: consent in Marketplace ([ADR-0008](0008-consent-and-permitted-field-matching.md)) and delegation encoded in context tokens ([ADR-0019](0019-organization-types-and-delegation.md)). Responses for other tenants' resources are 404.

## Alternatives considered

| Option | Why not |
|---|---|
| Code-level scoping only | One bug = a leak; not acceptable for the top characteristic |
| Database per tenant | Cross-tenant matching becomes very hard; operational overhead |

## Consequences

**Positive**: a leak requires two independent failures; isolation is verifiable.
**Negative**: RLS policies must be maintained with migrations; background jobs must set the tenant context explicitly.

## Compliance

FF-C1 (probe suite, 100 % of tenant endpoints), FF-C3 (RLS enabled on every tenant table), architecture test that tenant repositories require an `AccessContext`.

## Revisit when

A lender requires certified physical isolation (consider dedicated instances for that tenant's data).
