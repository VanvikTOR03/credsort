# 04 — Architecture Characteristics ("-ilities")

**Date:** 2026-11-19 · **Status:** Proposed · **Decision:** [ADR-0012](../adr/0012-driving-architecture-characteristics.md)

Architecture characteristics are the qualities the system must have that are *not* features: security, integrity, evolvability and so on. We identify candidates from requirements and business context, pick **at most three driving characteristics**, and make each one measurable with a **fitness function** (an automated or reviewable check).

## 1. Business drivers → characteristics

| Business driver (source) | Characteristic it implies |
|---|---|
| SMEs disclose confidential financials; "SME data sharing concerns" is a top risk (Master Plan §17) | **Confidentiality, privacy, consent** |
| A filter like "revenue > CHF 5M" already discloses information (Architecture Plan §6.1) | **Confidentiality** (indirect disclosure) |
| Assessments influence lending decisions; wrong mapping means a wrong score (risk table) | **Data integrity, correctness, reproducibility** |
| SMEs are now charged; fees must be exact and disclosed | **Integrity, auditability** |
| Revenue model still open; SME price TBD; tiers; lender fee to reconfirm | **Evolvability** (change pricing without code) |
| Abacus, bLink, fiduciary portal and an empirical benchmark are planned | **Evolvability, extensibility, interoperability** |
| "Every lender pays the same fee, no lender can buy a better position" (Brainstorming) | **Explainability / neutrality** |
| bexio may be unavailable; demo must work offline | **Fault tolerance, deployability** |
| API cost per loan belongs in unit economics (Gruber §6); "SLM is cheaper" | **Cost efficiency** |
| Two developers, AI-assisted, course deadlines | **Feasibility / simplicity** (constraint) |
| Small market at MVP stage (24,000 SMEs/year need financing in the whole Swiss market) | Scalability is **not** a driver |

## 2. Driving characteristics (top 3)

| Rank | Characteristic | Definition for CredSort | Fitness functions |
|---|---|---|---|
| 1 | **Confidentiality** (security + privacy + consent) | No organization can read or infer another organization's data except through an explicit, current, field-level consent. | Cross-tenant probe tests for every endpoint return 403/404; indirect-disclosure tests (counts, sorting, filters on non-permitted fields); secrets scanner in CI; no sensitive values in logs (log-scrubbing test) |
| 2 | **Data integrity** (correctness, reproducibility, auditability) | Financial values and fees are exactly right, reproducible from versioned inputs, and every critical change is audited. | Unit tests for every formula incl. boundary cases; reproducibility test (same snapshot + versions → identical `Decimal` result); accounting-invariant tests; DB constraint for a single selected offer; audit event written in the same transaction (test) |
| 3 | **Evolvability** (modifiability + extensibility) | Business rules that are expected to change (fees, plans, data sources, scorecard, channels) can change locally, ideally as configuration. | Changing a fee amount = new PriceBook version, **zero code change** (test); adding an `AccountingDataProvider` touches only `accounting/adapters`; import-linter module contracts pass; scorecard and mapping are versioned data |

**Constraint, not a characteristic: Feasibility / simplicity.** Two developers must deliver an end-to-end MVP. Every structural choice is checked against "can two people build, test and operate this?" This weighs heavily in the style selection ([05](05-architecture-style.md)).

*Change from the Architecture Plan v1:* it listed *simplicity* among the top three. Simplicity stays decisive, but as a constraint on how we build. Evolvability was promoted because the business model is visibly in flux, and SME charging was introduced after the plan was written.

## 3. Important but not driving

| Characteristic | Why it matters | How we address it |
|---|---|---|
| **Explainability / neutrality** | Trust and the "full neutrality" USP | Rule-based scorecard with factor explanations; deterministic, explained ranking ([ADR-0021](../adr/0021-matching-neutrality.md)) |
| **Testability** | Financial logic must be verified without bexio | Pure domain functions; synthetic adapter; test pyramid |
| **Interoperability** | Several accounting sources over time | Canonical ledger plus anti-corruption adapters ([ADR-0003](../adr/0003-ports-and-adapters.md)) |
| **Fault tolerance** | bexio or the LLM failing must not break the app | Timeouts, bounded retries, last valid snapshot, template fallback ([ADR-0007](../adr/0007-external-api-resilience.md)) |
| **Deployability / reproducibility** | A third person must run the demo from the README | Docker Compose, deterministic seed, offline mode ([ADR-0024](../adr/0024-deployment-and-demo-modes.md)) |
| **Cost efficiency** | AI and API costs per loan | Model as configuration, aggregates only, caching of explanations per assessment version |
| **Usability** | Consent steps add friction | "What lenders see" preview, sensible default allowlist |

## 4. Implicit characteristics (expected, not designed for specially)

Basic performance (dashboards and matching respond in about a second on demo data), maintainability, observability (structured logs without sensitive values), reasonable availability during demos.

## 5. Explicitly *not* driving now

| Characteristic | Why not now | Revisit when |
|---|---|---|
| Scalability / elasticity | Tens of SMEs and lenders in the MVP; no traffic spikes | Pilot shows sustained import or matching load |
| High availability (99.9 %+) | Demo and pilot tolerate maintenance windows | Real lenders depend on CredSort for daily operations |
| Independent deployability per module | One team, one release train | Team or regulatory needs require separate release cycles |
| Portability across clouds | One deployment target | Not foreseen |

## 6. Trade-offs between characteristics

| Tension | Resolution |
|---|---|
| Confidentiality ↔ Usability | Explicit consent steps stay, but with a preview and a safe default allowlist |
| Integrity ↔ Simplicity | Versioning snapshots, mappings, scorecards and price books costs effort; we accept it because silent recalculation would break reproducibility |
| Evolvability ↔ Simplicity | Ports only where an external dependency is unstable or an offline fallback is needed; no speculative abstractions |
| Explainability ↔ Predictive power | A rule-based scorecard over ML until real default data exist |
| Cost ↔ AI quality | Smallest model that passes the advisory evaluation tests |
| Fault tolerance ↔ Simplicity | In-process jobs with a restart-recovery rule instead of a queue broker |
