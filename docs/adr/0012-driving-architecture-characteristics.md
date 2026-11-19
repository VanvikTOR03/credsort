# ADR-0012: Driving Architecture Characteristics

| | |
|---|---|
| **Status** | Proposed — **changes** the top-3 list in Architecture Plan v1 §2.1 |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [04-architecture-characteristics.md](../architecture/04-architecture-characteristics.md), [ADR-0001](0001-modular-monolith.md) |

## Context

Architecture Plan v1 ranked **data integrity, security & confidentiality, simplicity** as its top characteristics. Since then:

- the team decided that **SMEs will be charged**, with amounts and triggers still open;
- the revenue model (lender fee, SME tiers, success fee) is visibly unsettled;
- Abacus, bLink, a fiduciary portal and an empirical benchmark are on the roadmap.

Simplicity remains essential, but it describes *how* we build with two people, not a quality the system shows to its users.

## Decision

**Driving characteristics (top 3), in priority order:**

1. **Confidentiality** (security, privacy, consent, tenant isolation, no indirect disclosure).
2. **Data integrity** (correct and reproducible financial values and fees; immutable, versioned records; auditability).
3. **Evolvability** (pricing, plans, data sources, scorecards and channels change locally, ideally as configuration).

**Constraint:** **Feasibility / simplicity.** Two developers must be able to build, test and operate everything. It is weighted as heavily as the top two in style selection.

**Important (not driving):** explainability/neutrality, testability, interoperability, fault tolerance, deployability, cost efficiency, usability.

**Explicitly not driving now:** scalability, elasticity, high availability, independent deployability.

## Alternatives considered

| Option | Why not |
|---|---|
| Keep "simplicity" as top-3 | It does not capture the business's need to change pricing and data sources cheaply; it is better expressed as a constraint. |
| Include scalability | Small volumes; it would push towards distributed styles with no benefit. |
| More than 3 driving characteristics | Dilutes trade-off decisions. |

## Consequences

**Positive**: style and design decisions have a clear tie-breaker; evolvability justifies versioned price books and adapter ports.
**Negative**: we deliberately accept limited scalability and availability until the pilot.

## Compliance

Each driving characteristic has fitness functions ([04 §2](../architecture/04-architecture-characteristics.md)). Every new ADR states which characteristics it supports or trades off.

## Revisit when

The pilot starts (availability and scalability may become driving); or the business model is finalized and becomes stable (evolvability may drop out of the top 3).
