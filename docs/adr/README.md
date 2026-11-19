# Architecture Decision Records (ADRs)

An ADR records one architecturally significant decision: its context, the alternatives, the decision, its consequences, how we check that we follow it (**compliance / fitness function**) and when to reconsider it.

## Process

1. Copy [`template.md`](template.md) to `NNNN-short-title.md` (next free number, never reused).
2. Open a PR. The second developer reviews; decisions touching the financial model or access control **require** review by both.
3. On approval, change the status from **Proposed** to **Accepted** and set an owner.
4. Never edit an accepted decision's substance. Write a new ADR that **supersedes** it and mark the old one `Superseded by ADR-XXXX`.

## Index

All ADRs were written on 2026-11-19 and are **Proposed** until the team accepts them. ADR-0001 to ADR-0011 formalize the register in the Architecture Plan v1 (§10), updated where the review found gaps. ADR-0012 to ADR-0024 are new ([review](../architecture/01-architecture-review.md)).

### Foundations

| ADR | Decision |
|---|---|
| [0012](0012-driving-architecture-characteristics.md) | Driving characteristics: **Confidentiality, Data integrity, Evolvability**; Feasibility is a constraint |
| [0001](0001-modular-monolith.md) | **Domain-partitioned modular monolith** with ports & adapters at the edges; one quantum |
| [0002](0002-six-domain-modules.md) | **Six modules**: access, accounting, analysis, lending, advisory, billing; acyclic dependencies |
| [0003](0003-ports-and-adapters.md) | Ports only for unstable external dependencies: accounting data, LLM, KYB, payments |
| [0004](0004-single-postgresql-and-table-ownership.md) | One PostgreSQL, schema per module, single table ownership, no cross-schema FKs |

### Integration and runtime

| ADR | Decision |
|---|---|
| [0005](0005-sync-use-cases-and-background-import.md) | Synchronous use cases; in-process background imports with 202 + polling |
| [0006](0006-http-json-api-and-openapi-contract.md) | Resource-oriented HTTP/JSON, contract-first OpenAPI, problem+json errors |
| [0007](0007-external-api-resilience.md) | Timeouts, bounded retries, fallbacks for bexio and the LLM |
| [0010](0010-import-recovery-and-idempotency.md) | Interrupted imports become FAILED; idempotent, atomic imports |
| [0011](0011-transaction-boundaries-and-offer-concurrency.md) | One transaction per use case; at most one selected offer (lock + partial unique index) |
| [0023](0023-in-process-domain-events.md) | In-process domain events after commit; critical writes stay in the transaction |
| [0024](0024-deployment-and-demo-modes.md) | Docker Compose; offline and live demo modes; Swiss/EU hosting for the pilot |

### Data, money and AI

| ADR | Decision |
|---|---|
| [0015](0015-money-and-financial-calculations.md) | Decimal-only money, CHF, rounding at boundaries, unavailable ≠ 0, versioned formulas |
| [0009](0009-ai-explains-deterministic-results.md) | AI explains, never calculates; aggregates only; model is configuration (SLM allowed) |
| [0022](0022-offer-data-for-rate-benchmark.md) | Immutable offer history linked to assessments; anonymized aggregates (k ≥ 5) for the benchmark |

### Security, privacy and trust

| ADR | Decision |
|---|---|
| [0008](0008-consent-and-permitted-field-matching.md) | Consent and permitted-field matching; no indirect disclosure |
| [0016](0016-authentication.md) | Built-in session auth for the MVP (works offline); OIDC + MFA before the pilot |
| [0017](0017-tenant-isolation.md) | Tenant-scoped repositories + probe tests now; PostgreSQL RLS before real data |
| [0020](0020-kyb-outsourced-via-port.md) | KYB outsourced via a port; stub in the MVP; pilot loan cap |
| [0021](0021-matching-neutrality.md) | Ranking is a pure function of lender criteria and permitted fields; no paid placement |

### Business model and channels

| ADR | Decision |
|---|---|
| [0013](0013-billing-and-sme-charging.md) | **SMEs are charged**: versioned price books, fee ledger, disclosure before action; amounts TBD |
| [0014](0014-no-loan-money-flow.md) | CredSort never holds or moves loan money; it invoices only its own fees |
| [0019](0019-organization-types-and-delegation.md) | Organization types, fiduciary delegation and referral attribution modelled now |

### Frontend

| ADR | Decision |
|---|---|
| [0018](0018-single-nextjs-app-with-portals.md) | One Next.js app; SME/Lender/Admin portals as route groups; `/api` proxy; generated client |
