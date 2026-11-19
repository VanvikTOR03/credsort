# Architecture Decision Records (ADRs)

An ADR records one architecturally significant decision: its context, the alternatives, the decision, its consequences, how we check that we follow it (**compliance / fitness function**) and when to reconsider it.

## Process

1. Copy [`template.md`](template.md) to `NNNN-short-title.md` (next free number, never reused).
2. Open a PR. Decisions touching the financial model, money, consent or access control require **two** approvals.
3. On approval, change the status from **Proposed** to **Accepted** and set an owner.
4. Never edit an accepted decision's substance. Write a new ADR that **supersedes** it and mark the old one `Superseded by ADR-XXXX`.

## Change log

| Date | Revision | Change |
|---|---|---|
| 2026-11-19 | 1 (commit `f45046c`) | 24 ADRs for a modular monolith with six modules |
| 2026-11-19 | **2 (this)** | Architecture re-selected purely on characteristics (feasibility removed as a constraint): **service-based backbone + event-driven integration + plug-in edges + financial data pipeline**. ADRs rewritten (all still *Proposed*, none had been accepted); 0025–0031 added. Renamed: 0001, 0002, 0003, 0004, 0005, 0006, 0007, 0011, 0018, 0023, 0024. |

## Index

All ADRs are **Proposed** until the team accepts them.

### Foundations

| ADR | Decision |
|---|---|
| [0012](0012-driving-architecture-characteristics.md) | Driving characteristics: **Confidentiality, Data integrity, Evolvability**; implementation effort is not a criterion |
| [0001](0001-architecture-style.md) | **Service-based backbone + event-driven integration + plug-in edges + pipeline**; why not monolith, microservices or pure event-driven |
| [0002](0002-service-decomposition.md) | Six domain services (Identity, Accounting Integration, Financial Intelligence, Marketplace, Billing, Advisory) + Notification + Audit; consent lives in Marketplace |
| [0004](0004-database-per-service.md) | A database per service; no shared tables or cross-database keys; RLS inside |
| [0003](0003-plug-in-extension-points.md) | Plug-in ports for every external provider and replaceable rule set |
| [0030](0030-repository-and-shared-libraries.md) | Monorepo, `contracts/` folder, technical-only shared library, one pipeline per service |

### Integration and consistency

| ADR | Decision |
|---|---|
| [0023](0023-event-driven-integration.md) | Transactional outbox → RabbitMQ (quorum queues, DLQ) → idempotent inbox; thin CloudEvents; claim check |
| [0011](0011-consistency-model.md) | Strong consistency inside a service (selection, publication); guaranteed-eventual across services; reconciliation jobs |
| [0006](0006-api-contracts.md) | Per-service OpenAPI; external vs internal APIs; problem+json; decimal strings; consumer-driven contract tests |
| [0007](0007-resilience.md) | Timeouts, idempotent retries, circuit breakers, bulkheads; defined fallbacks; Billing fails closed |
| [0005](0005-import-workers.md) | Asynchronous imports on dedicated workers; 202 + polling |
| [0010](0010-import-recovery-and-idempotency.md) | Lease-based job claiming, recovery and idempotent batches |
| [0025](0025-financial-data-pipeline.md) | Pipes-and-filters pipeline: fetch → normalize → validate → map → metrics → assess; versioned and reproducible |
| [0026](0026-published-profile-snapshots.md) | Permitted fields frozen as a PublishedProfile at publication; matching never reads live Intelligence data |

### Security, privacy and trust

| ADR | Decision |
|---|---|
| [0016](0016-authentication.md) | Keycloak (OIDC + MFA); tokens kept server-side in the BFF |
| [0027](0027-context-tokens-and-service-trust.md) | Identity-issued context tokens (about 2 min) + deny-list; service tokens; allowed-caller lists; mTLS in the pilot |
| [0017](0017-tenant-isolation.md) | Scoped repositories + PostgreSQL RLS from day one + cross-tenant probe suite |
| [0008](0008-consent-and-permitted-field-matching.md) | Consent in Marketplace; matching only on permitted fields; no indirect disclosure |
| [0021](0021-matching-neutrality.md) | Ranking depends only on lender criteria and the published profile; no paid placement |
| [0020](0020-kyb-outsourced-via-port.md) | KYB plug-in in Identity; status as a token claim; pilot loan cap |
| [0028](0028-central-audit-log.md) | Local audit in every transaction + central append-only, hash-chained log |
| [0031](0031-data-lifecycle-and-deletion.md) | Coordinated deletion/anonymization across services; tombstones prevent resurrection on replay |

### Data, money and AI

| ADR | Decision |
|---|---|
| [0015](0015-money-and-financial-calculations.md) | Decimal-only money, CHF, rounding at boundaries, unavailable ≠ 0, decimal strings in APIs and events |
| [0009](0009-ai-explains-deterministic-results.md) | AI explains only; Advisory has no access to financial databases; model is a plug-in (SLM allowed) |
| [0022](0022-offer-data-for-rate-benchmark.md) | Immutable offer history; anonymized aggregates (≥ 5 offers, ≥ 3 lenders) for the benchmark |

### Business model and channels

| ADR | Decision |
|---|---|
| [0013](0013-billing-and-sme-charging.md) | **SMEs are charged**: versioned price books, **signed quotes**, charges exactly as quoted; amounts TBD |
| [0014](0014-no-loan-money-flow.md) | CredSort never holds or moves loan money; it invoices only its own fees |
| [0019](0019-organization-types-and-delegation.md) | Organization types, fiduciary delegation and referral attribution from day one |

### Web, deployment and operations

| ADR | Decision |
|---|---|
| [0018](0018-web-app-and-bff.md) | One Next.js app as BFF; portals as route groups; services unreachable from the browser |
| [0024](0024-deployment.md) | Docker Compose (offline/live demo profiles); managed Kubernetes in Switzerland/EU for the pilot |
| [0029](0029-observability.md) | OpenTelemetry across HTTP and messages; allowlist logging; consistency-model alerts |
