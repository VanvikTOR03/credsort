# 01 — Architecture Review

**Date:** 2026-11-19 · **Revision:** 2 · **Status:** Proposed for team approval

## Inputs reviewed

| Source | What it contributed |
|---|---|
| `docs/CredSort_Master_Product_Development_Plan_EN_v1.md` | Product concept, P0/P1/P2 features, revenue working assumptions, product milestones M0–M10 |
| `docs/CredSort_Architecture_Implementation_Plan_EN_v1.md` | Modular monolith, five modules, ports & adapters, consent model, transactions, ADR register 0001–0011 |
| `docs/CredSort_Diagrams_as_Code_EN.md` | Context, container, sequence, ER and state diagrams |
| OneNote · GENERAL · *Feedback Gruber* | Go-to-market, anchor investors, SMEs paying, credit risk / fraud, number consistency, API cost per loan |
| OneNote · WORKSTREAMS · *Business Model [Seb]* | Business Model Canvas, Basic/Light/Pro tiers, fiduciary 20 % revenue share, margin notes (SLM, outsource KYC) |
| OneNote · WORKSTREAMS · *Brainstorming [Seb]* | Market size, competitors (Systemcredit, Compeon, Swisspeers, credit bureaus), USPs, "benchmark data is the moat" |
| Team decision, 2026-11-19 | **SMEs will be charged.** Amount and trigger to be decided later. |
| Stakeholder direction, 2026-11-19 | **Choose the architecture purely on architecture characteristics.** Team size and implementation effort are not constraints. |

## How the decision evolved

| Revision | Style | Reason |
|---|---|---|
| v1 plan | Modular monolith, five modules | Simplicity for two developers was a top-3 characteristic |
| Revision 1 (commit `f45046c`) | Modular monolith, six modules (`billing` added) | Same feasibility constraint, plus SME charging |
| **Revision 2 (this)** | **Service-based + event-driven + microkernel + pipeline** | Feasibility removed as a constraint → the style is chosen on confidentiality, integrity and evolvability alone ([05](05-architecture-style.md)) |

The domain analysis, the business rules (consent, neutrality, no money flow, money handling, AI explains only) and the gap list below are unchanged by this switch. Only the **structure** changed.

## What holds up from the v1 plans (kept)

1. **Financial Assessment ≠ Data Confidence ≠ Match ranking**, a separation that protects both integrity and neutrality.
2. **Consent by design**, including protection against *indirect* disclosure through filters, counts and ranking → [ADR-0008](../adr/0008-consent-and-permitted-field-matching.md)
3. **Immutable, versioned snapshots and assessments** → [ADR-0015](../adr/0015-money-and-financial-calculations.md), [ADR-0025](../adr/0025-financial-data-pipeline.md)
4. **A synthetic data path first**; bexio problems never block the product → [ADR-0003](../adr/0003-plug-in-extension-points.md)
5. **AI only explains**; deterministic engines calculate → [ADR-0009](../adr/0009-ai-explains-deterministic-results.md)
6. **One transaction for offer selection** with a database guarantee of a single selected offer → [ADR-0011](../adr/0011-consistency-model.md)

## Gaps found and how they are resolved

| # | Finding | Why it matters | Resolution |
|---|---|---|---|
| G1 | **SMEs will now be charged**, but the plans say "SME access: free". Nothing owns pricing, fees, plans (Basic/Light/Pro) or entitlements. | A "TBD" revenue model must not require code changes; fees must be disclosed before the SME commits. | **Billing service** with versioned price books, **signed quotes** and an immutable fee ledger → [ADR-0013](../adr/0013-billing-and-sme-charging.md) |
| G2 | **The money flow is undefined.** Gruber's "servicing fee for payment processing and collections" implies handling repayments. | Holding or forwarding third-party funds is likely to make CredSort a regulated financial intermediary (legal review required); it contradicts "CredSort never lends". | **CredSort stays out of the money flow** → [ADR-0014](../adr/0014-no-loan-money-flow.md) |
| G3 | **Authentication is not specified.** | Confidentiality is the top characteristic. | Keycloak (OIDC + MFA from day one), BFF keeps tokens server-side, identity-issued context tokens → [ADR-0016](../adr/0016-authentication.md), [ADR-0027](../adr/0027-context-tokens-and-service-trust.md) |
| G4 | **Tenant isolation is code-level only.** | One missing filter leaks a competitor's financials. | Database per service + scoped queries + **row-level security from day one** + probe tests → [ADR-0004](../adr/0004-database-per-service.md), [ADR-0017](../adr/0017-tenant-isolation.md) |
| G5 | **Money rules are incomplete.** | Fees are invoiced and ratios drive assessments. | → [ADR-0015](../adr/0015-money-and-financial-calculations.md) |
| G6 | **Fiduciaries are the main acquisition channel** but sit at P2 with no data model. | The 20 % revenue share needs referral attribution from the first SME onboarded. | Organization types, delegation and referral attribution in Identity now → [ADR-0019](../adr/0019-organization-types-and-delegation.md) |
| G7 | **KYC/KYB and fraud** (Gruber §4; "outsource the KYC risk") are absent. | Adverse selection is the top credit risk raised in feedback. | KYB plug-in, stub in the MVP, pilot loan cap → [ADR-0020](../adr/0020-kyb-outsourced-via-port.md) |
| G8 | **Neutrality is a USP** but not enforced anywhere. | It must hold in code. | Marketplace matching never receives billing data → [ADR-0021](../adr/0021-matching-neutrality.md) |
| G9 | **Benchmark data is "the moat"**, but there is no retention or aggregation policy. | Without immutable linked offers the moat never accumulates. | → [ADR-0022](../adr/0022-offer-data-for-rate-benchmark.md) |
| G10 | **Notifications** ("offer available", refinancing alerts) have no mechanism. | Side effects must not create hidden coupling or lost writes. | Event-driven integration with outbox/inbox; a Notification service → [ADR-0023](../adr/0023-event-driven-integration.md) |
| G11 | **Frontend structure** is undecided. | Affects cookies, tokens, CSRF. | One Next.js app as BFF; tokens never in the browser → [ADR-0018](../adr/0018-web-app-and-bff.md) |
| G12 | **Driving characteristics** included "simplicity". | It is a constraint, and stakeholders removed it. | Top 3: Confidentiality, Data integrity, Evolvability → [ADR-0012](../adr/0012-driving-architecture-characteristics.md) |
| G13 | **Hosting and data residency** are unspecified. | Real SME financials fall under the Swiss nFADP. | → [ADR-0024](../adr/0024-deployment.md) |
| G14 | **"Can we use an SLM, it is cheaper?"** | AI cost per loan is part of unit economics (Gruber §6). | Model as a plug-in, gated by an evaluation suite → [ADR-0009](../adr/0009-ai-explains-deterministic-results.md) |
| G15 | **No activity history** across the system, although SMEs should see who used their data. | Auditability and trust. | Local audit in every service + central tamper-evident log → [ADR-0028](../adr/0028-central-audit-log.md) |
| G16 | **No data lifecycle** (retention, deletion, anonymization). | nFADP rights vs the benchmark's need to keep offers. | → [ADR-0031](../adr/0031-data-lifecycle-and-deletion.md) |
| G17 | **Consistency across a distributed design** must be explicit. | Distributed systems fail in partial ways. | Strong-vs-eventual matrix, reconciliation jobs, failure analysis → [ADR-0011](../adr/0011-consistency-model.md), [07](07-failure-modes-and-risks.md) |

## Inconsistencies in the source documents (need an owner, not architecture)

| Topic | Conflict | Recommendation |
|---|---|---|
| Revenue model | Pitch deck: lender pays 0.75 % (min CHF 2,000, cap CHF 7,500), SME free. Seb: SME tiers. Gruber: SME success fee (2 % example) + servicing fee. **Team: SMEs will be charged.** | Billing supports every option as configuration; the team still decides (a) the SME fee and trigger, (b) whether the lender fee remains. |
| Milestone numbering | Architecture Plan M0–M8 (technical) vs Master Plan M0–M10 (product). | Prefix: **T-M#** vs **P-M#**. |
| Market size | 161,000 SMEs (count) vs CHF 562B (volume) appear side by side. | Keep counts and CHF amounts separate (Gruber §5). |
| v1 technical milestones | Written for a monolith (one skeleton, one backend). | Re-plan milestones per service once the ADRs are accepted (not done here; no coding yet). |
