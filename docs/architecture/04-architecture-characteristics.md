# 04 — Architecture Characteristics ("-ilities")

**Date:** 2026-11-19 · **Revision:** 2 · **Status:** Proposed · **Decision:** [ADR-0012](../adr/0012-driving-architecture-characteristics.md)

Architecture characteristics are the qualities the system must have that are not features. We pick **three driving characteristics**, make every characteristic measurable through **fitness functions** (automated or reviewable checks), and use them as the only criteria for structural decisions.

> **Revision 2:** Revision 1 treated feasibility (a two-person team) as a hard constraint. Stakeholders removed it. Implementation effort and team size are **not** evaluation criteria.

## 1. Business drivers → characteristics

| Business driver (source) | Characteristic |
|---|---|
| SMEs disclose confidential financials; "SME data sharing concerns" is a top risk (Master Plan §17) | **Confidentiality** |
| "Revenue > CHF 5M" as a filter already discloses information (Architecture Plan §6.1) | **Confidentiality** (indirect disclosure) |
| Assessments influence lending decisions; wrong mapping means a wrong score | **Data integrity**, reproducibility |
| SMEs are now charged; fees must be exact and disclosed | **Data integrity**, auditability |
| Revenue model open; SME price TBD; tiers; lender fee to reconfirm | **Evolvability** |
| Abacus, bLink, fiduciary portal, empirical benchmark planned | **Evolvability**, interoperability |
| "No lender can buy a better position" | Explainability / neutrality |
| bexio or LLM unavailable; demo must also run offline | Fault tolerance |
| SMEs should see who used their data | Auditability |
| API cost per loan in unit economics (Gruber §6); "SLM is cheaper" | Cost efficiency |
| Small market at MVP stage | Scalability is **not** a driver |

## 2. Driving characteristics (top 3)

| Rank | Characteristic | Definition for CredSort |
|---|---|---|
| 1 | **Confidentiality** (security, privacy, consent) | No organization can read or infer another organization's data except through an explicit, current, field-level consent. Every component sees only the data it needs. |
| 2 | **Data integrity** (correctness, reproducibility, auditability) | Financial values and fees are exactly right, reproducible from versioned inputs, never lost or duplicated across services, and every critical action is audited. |
| 3 | **Evolvability** (modifiability, extensibility, deployability) | Business rules expected to change (fees, plans, data sources, scorecards, channels, AI models) change locally, ideally as configuration, and services can be changed and deployed independently. |

## 3. Important (not driving)

| Characteristic | Definition | Primary mechanisms |
|---|---|---|
| **Fault tolerance** | Failure of one service or provider does not stop unrelated user journeys | Service isolation, outbox/inbox, timeouts, circuit breakers, fallbacks ([ADR-0007](../adr/0007-resilience.md)) |
| **Auditability** | Every critical action is traceable to a person, organization and time | Local audit + central tamper-evident log ([ADR-0028](../adr/0028-central-audit-log.md)) |
| **Explainability / neutrality** | Assessments and rankings can be explained; nothing commercial influences ranking | Rule-based scorecards, explained matching ([ADR-0021](../adr/0021-matching-neutrality.md)) |
| **Testability** | Each rule and each service is testable in isolation | Pure pipeline filters, contract tests, synthetic data |
| **Interoperability** | New external providers can be added | Plug-in ports ([ADR-0003](../adr/0003-plug-in-extension-points.md)) |
| **Observability** | A flow can be followed across services and messages | OpenTelemetry, correlation IDs ([ADR-0029](../adr/0029-observability.md)) |
| **Cost efficiency** | AI and provider cost per loan is controlled | Model as configuration, caching, aggregates only |
| **Usability** | Consent and fee steps are understandable | Previews, signed quotes shown in plain language |

## 4. Implicit, and explicitly not driving now

| Characteristic | Status | Revisit when |
|---|---|---|
| Basic performance (screens respond in about 1 s on demo data) | Implicit | — |
| Maintainability | Implicit | — |
| Scalability / elasticity | **Not driving**: tens of organizations in the MVP | Pilot shows sustained load |
| High availability (99.9 %+) | **Not driving** in the MVP; Identity is engineered for HA anyway | Lenders depend on CredSort daily |
| Portability across clouds | Not needed | — |

## 5. Fitness functions (consolidated catalogue)

Each check runs in CI unless marked *review* or *runtime*.

### Confidentiality

| ID | Check |
|---|---|
| FF-C1 | **Cross-tenant probe suite**: every external endpoint of every service is called with another tenant's IDs → 404/403 |
| FF-C2 | **Indirect-disclosure suite**: lender criteria on a non-permitted field yield results, counts and order identical to the application not existing |
| FF-C3 | **RLS enabled** on every tenant table (schema inspection test per service DB) |
| FF-C4 | **Network test**: internal APIs (`/internal/*`) and databases are unreachable from the edge and from non-allowed services |
| FF-C5 | **Event payload scan**: event JSON Schemas contain no fields from the strictly-confidential catalogue |
| FF-C6 | **Log/trace scrubbing**: a test injects sentinel values into requests and asserts they never appear in logs or spans |
| FF-C7 | Secrets scanner on every commit; no tokens in browser storage (*E2E check*) |
| FF-C8 | Advisory service has **no** database credentials for financial databases (*deployment config test*) |

### Data integrity

| ID | Check |
|---|---|
| FF-I1 | Unit tests for every financial formula, including boundary values and unavailable inputs |
| FF-I2 | **Reproducibility**: same batch + mapping + formula + scorecard versions → byte-identical assessment |
| FF-I3 | Concurrency test: two simultaneous selections → exactly one succeeds |
| FF-I4 | **Duplicate delivery test**: every consumer processes a replayed event without side effects (inbox) |
| FF-I5 | Quote = charge: for every fee-bearing action, the recorded charge equals the signed quote |
| FF-I6 | *Runtime* **reconciliation jobs** report zero mismatches (selections ↔ charges, batches ↔ snapshots, local ↔ central audit) |
| FF-I7 | Audit hash chain verifies end to end (*runtime, daily*) |
| FF-I8 | No `float` in domain code handling money or ratios |

### Evolvability

| ID | Check |
|---|---|
| FF-E1 | Changing a fee amount = activating a new price-book version with **zero code change** |
| FF-E2 | Adding an accounting provider touches only Accounting's plug-in folder (*review*) |
| FF-E3 | **Contract tests** (consumer-driven) pass for every internal API and event before a service deploys |
| FF-E4 | Event schemas evolve **backward-compatibly** (schema diff check) |
| FF-E5 | Each service builds, tests and deploys **alone** (its pipeline does not require other services' code) |
| FF-E6 | **Sync dependency graph** has no cycles and no request path longer than two hops (static check of declared clients) |
| FF-E7 | Shared libraries contain no domain logic (*review* + import rules) |

### Supporting characteristics

| ID | Check |
|---|---|
| FF-F1 | Fault injection: bexio 429/5xx/timeouts, LLM timeouts, broker down, Billing down → expected fallbacks ([07](07-failure-modes-and-risks.md)) |
| FF-F2 | Ranking is deterministic and unaffected by any billing data (property test) |
| FF-F3 | Every inbound request and message carries a trace context (*runtime sampling*) |
| FF-F4 | Advisory output contains no number absent from its input context |

## 6. Trade-offs between characteristics

| Tension | Resolution |
|---|---|
| Confidentiality ↔ Usability | Explicit consent and MFA stay; previews and sensible defaults reduce friction |
| Integrity ↔ Fault tolerance | Critical invariants stay inside one service (strong); cross-service effects are eventual but guaranteed (outbox, inbox, reconciliation) |
| Integrity ↔ Evolvability | Versioning everything (pipeline, price books, schemas) costs effort but keeps old results reproducible while rules change |
| Confidentiality ↔ Evolvability | Thin events force consumers to fetch details through authorized APIs, which adds coupling but keeps sensitive data in one place |
| Fault tolerance ↔ Integrity (fees) | Fee-bearing actions **fail closed** without a valid quote: availability is sacrificed rather than charging an undisclosed fee |
| Explainability ↔ Predictive power | Rule-based scorecards until real outcome data exist |
| Cost ↔ AI quality | Smallest model that passes the advisory evaluation suite |
