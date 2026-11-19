# ADR-0017: Tenant Isolation — Scoped Repositories and Probe Tests Now, Row-Level Security Before Real Data

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0004](0004-single-postgresql-and-table-ownership.md), [ADR-0008](0008-consent-and-permitted-field-matching.md), [ADR-0016](0016-authentication.md) |

## Context

All tenants (SMEs, lenders, fiduciaries) share one database. Architecture Plan v1 enforces boundaries in code only. A single forgotten `WHERE organization_id = …` would expose a company's financials to a competitor or a bank, which is the worst possible failure for CredSort.

## Decision

**Now (MVP)**
1. Every tenant-owned table has an `organization_id` (owner) column.
2. Repositories for tenant data **require an `AccessContext`** argument and apply the scope themselves. There are **no unscoped query methods** for tenant tables (platform-admin queries live in a separate, explicitly named admin repository).
3. Cross-organization access (lender → SME application) happens **only** through `access.api` consent checks ([ADR-0008](0008-consent-and-permitted-field-matching.md)) or delegation ([ADR-0019](0019-organization-types-and-delegation.md)).
4. For resources of other tenants, the API returns **404** (do not reveal existence).
5. **Probe tests:** a parametrized test suite calls every endpoint with IDs belonging to another tenant and expects 404/403.

**Before the pilot (defense in depth)**
6. Enable **PostgreSQL row-level security** on tenant tables, using a per-transaction setting (e.g. `SET LOCAL app.org_id`) and policies that match the repository scope. The application's DB role must not bypass RLS.

## Alternatives considered

| Option | Why not |
|---|---|
| RLS from day one | Stronger, but adds complexity to migrations, tests and admin tooling during rapid MVP iteration with synthetic data. |
| Database or schema per tenant | Operationally heavy; matching across tenants becomes hard. |
| Rely on code review only | Not a reliable control for the top characteristic. |

## Consequences

**Positive**: a strong guarantee now via structure plus tests; a clear upgrade path.
**Negative**: until RLS, a bug in a scoped repository is caught only by tests; admin queries need a separate path.

## Compliance

- The probe-test suite runs in CI and covers 100 % of tenant-data endpoints (a new endpoint without a probe test fails a coverage check).
- Architecture test: tenant repositories' public methods take an `AccessContext`.
- Pilot checklist item: RLS enabled and tested before real data.

## Revisit when

Pilot preparation (enable RLS); or a lender requires certified isolation (consider separate databases for sensitive tenants).
