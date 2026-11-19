# ADR-0004: One PostgreSQL Database, Schema per Module, Single Table Ownership

| | |
|---|---|
| **Status** | Proposed — formalizes Architecture Plan v1 §4.1 and adds the cross-schema FK rule |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0001](0001-modular-monolith.md), [ADR-0011](0011-transaction-boundaries-and-offer-concurrency.md), [ADR-0017](0017-tenant-isolation.md) |

## Context

Integrity needs local transactions and constraints. Evolvability needs modules that could later be extracted without untangling a shared data model.

## Decision

- **One PostgreSQL instance**, with **one schema per module**: `access`, `accounting`, `analysis`, `lending`, `billing`. `advisory` has no tables in the MVP.
- **Single table ownership:** only the owning module reads and writes its tables. Other modules use the owner's `api.py`.
- **No foreign keys across schemas.** Cross-module references are stored as UUIDs and validated by the owning module's API. Within a schema, foreign keys and constraints are used fully.
- Organizations and users are never hard-deleted (soft delete), so cross-module references cannot dangle.
- **Alembic** with one migration history; each migration touches exactly one schema.
- Amounts use `NUMERIC` types ([ADR-0015](0015-money-and-financial-calculations.md)); all primary keys are UUIDs.

## Alternatives considered

| Option | Why not |
|---|---|
| One schema, shared tables | Boundaries invisible; extraction later becomes very expensive. |
| Database per module | Distributed transactions for selection + fee + audit; operational overhead. |
| Cross-schema foreign keys | Stronger referential integrity, but welds modules together at the database level and blocks extraction. Soft deletes plus API validation cover the risk. |

## Consequences

**Positive**: ACID across modules in one transaction; clear ownership; a later split is feasible.
**Negative**: no DB-enforced referential integrity across modules; schemas organize but **do not secure** (one DB role sees all) → see [ADR-0017](0017-tenant-isolation.md).

## Compliance

- Architecture test: SQL/ORM models of module X reference only schema X.
- Migration review checklist: one schema per migration, no cross-schema FK.

## Revisit when

A module is extracted into a service (it takes its schema with it), or separate DB roles per module become necessary for the pilot.
