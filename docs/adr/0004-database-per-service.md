# ADR-0004: A Database per Service, No Shared Tables, Row-Level Security Inside

| | |
|---|---|
| **Status** | Proposed — replaces "one PostgreSQL, schema per module" (v1 §4.1, Revision 1) |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0001](0001-architecture-style.md), [ADR-0011](0011-consistency-model.md), [ADR-0017](0017-tenant-isolation.md), [ADR-0031](0031-data-lifecycle-and-deletion.md) |

## Context

Confidentiality needs least privilege: a component should be technically unable to read data it does not own. Evolvability needs services whose schemas can change without coordinating with other teams' code.

## Decision

- **Every service owns exactly one PostgreSQL database** with its own credentials. No other service has credentials for it.
- **No shared tables, no cross-database queries, no cross-database foreign keys.** References to other services' entities are UUIDs, validated through their APIs or events.
- Inside a database: full use of foreign keys, check constraints, partial unique indexes and **row-level security** on tenant tables ([ADR-0017](0017-tenant-isolation.md)).
- Every producing service has `outbox` and every consuming service has `inbox` tables ([ADR-0023](0023-event-driven-integration.md)).
- Migrations are owned per service and follow **expand → migrate → contract**.
- Locally, one PostgreSQL container hosts all databases with one role per database. In the pilot, the databases holding C4/C3 data (Accounting, Intelligence, Marketplace) run on **separate instances**.
- Organizations are never hard-deleted while references exist; deletion follows the lifecycle flow ([ADR-0031](0031-data-lifecycle-and-deletion.md)).
- Money and ratios use `NUMERIC` ([ADR-0015](0015-money-and-financial-calculations.md)); primary keys are UUIDs.

## Alternatives considered

| Option | Why not |
|---|---|
| One database, schema per service | One credential compromise or misconfiguration exposes everything; schemas organize but do not isolate |
| Shared tables | Hidden coupling; impossible independent evolution |
| Database per tenant | Cross-tenant matching becomes very hard; operational overhead without a confidentiality gain over RLS + DB per service |

## Consequences

**Positive**: real isolation; a small blast radius; independent schema evolution.
**Negative**: no cross-service joins (data is fetched by API or projected); restoring one database needs replay and reconciliation ([07](../architecture/07-failure-modes-and-risks.md) R-I8).

## Compliance

- FF-C4: each service's credentials connect only to its own database (deployment test).
- FF-C3: RLS enabled on every tenant table (schema inspection).
- Migration review: one service per migration, no cross-database references.

## Revisit when

A reporting need spans services (build a dedicated read model fed by events, never cross-database queries).
