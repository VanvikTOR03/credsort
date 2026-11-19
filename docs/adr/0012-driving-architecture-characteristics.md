# ADR-0012: Driving Architecture Characteristics

| | |
|---|---|
| **Status** | Proposed — changes the top-3 list of Architecture Plan v1 §2.1 and Revision 1 |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [04-architecture-characteristics.md](../architecture/04-architecture-characteristics.md), [ADR-0001](0001-architecture-style.md) |

## Context

- v1 ranked **data integrity, security & confidentiality, simplicity** as top characteristics.
- Revision 1 kept simplicity/feasibility as a hard constraint (a two-person team).
- Stakeholder direction (2026-11-19): **implementation capacity is not a constraint; decide on architecture characteristics alone.**
- The team decided that SMEs will be charged (amounts TBD); the revenue model, data sources and channels are still moving.

## Decision

**Driving characteristics, in priority order:**

1. **Confidentiality** (security, privacy, consent, tenant isolation, least privilege, no indirect disclosure).
2. **Data integrity** (correct, reproducible values and fees; no lost or duplicated effects across services; complete audit).
3. **Evolvability** (rules and providers change locally, ideally as configuration; services change and deploy independently).

**Important (not driving):** fault tolerance, auditability, explainability/neutrality, testability, interoperability, observability, cost efficiency, usability.

**Not driving now:** scalability, elasticity, high availability beyond Identity, portability.

**Not a criterion:** implementation effort and team size.

Each characteristic is verified by fitness functions ([04 §5](../architecture/04-architecture-characteristics.md)).

## Alternatives considered

| Option | Why not |
|---|---|
| Keep simplicity/feasibility as a constraint | Removed by stakeholder direction |
| Fault tolerance as a top-3 characteristic | Important, but a temporary outage is less harmful than a leak or a wrong fee; it is served largely by the chosen style anyway |
| More than three driving characteristics | Dilutes trade-off decisions |

## Consequences

**Positive**: one clear tie-breaker for every structural decision; justifies service isolation, versioned rules and plug-ins.
**Negative**: we knowingly accept higher operational cost and complexity, and limited scalability planning.

## Compliance

Every ADR states which driving characteristics it supports or trades off. Fitness functions FF-C*, FF-I*, FF-E* run in CI or as runtime checks.

## Revisit when

The pilot starts (availability may become driving); or the business model stabilizes (evolvability may drop out of the top 3).
