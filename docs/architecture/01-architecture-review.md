# 01 — Architecture Review

**Date:** 2026-11-19 · **Status:** Proposed for team approval

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

## Verdict

The existing baseline is **sound and should be kept**: a modular monolith with explicit module boundaries, ports & adapters only at unstable external edges, consent-by-design and deterministic, versioned financial calculations. It fits a two-person team building a confidential, correctness-critical MVP.

The review found **gaps where the business model meets the architecture**. The plans were written when SMEs were free and fiduciaries were "later". Both have since changed in the team's thinking. The gaps below are resolved by new or updated ADRs.

## What holds up (keep as is)

1. **Modular monolith, one quantum.** Offer selection, fee recording and audit need ACID transactions. The volume is small and the team is two people. → [ADR-0001](../adr/0001-modular-monolith.md)
2. **Financial Assessment ≠ Data Confidence ≠ Match ranking.** This separation protects both integrity and neutrality.
3. **Consent by design**, including protection against *indirect* disclosure through filters, counts and ranking. → [ADR-0008](../adr/0008-consent-and-permitted-field-matching.md)
4. **Immutable, versioned snapshots and assessments.** Same inputs plus same versions give the same result. → [ADR-0015](../adr/0015-money-and-financial-calculations.md)
5. **Synthetic path first.** A bexio problem never blocks the MVP. → [ADR-0003](../adr/0003-ports-and-adapters.md)
6. **AI only explains**; deterministic engines calculate. → [ADR-0009](../adr/0009-ai-explains-deterministic-results.md)

## Gaps found and how they are resolved

| # | Finding | Why it matters | Resolution |
|---|---|---|---|
| G1 | **SMEs will now be charged**, but the plans say "SME access: free". Nothing in the architecture owns pricing, fees, plans (Basic/Light/Pro) or entitlements. | A revenue model that is "TBD" must not require code changes every time it changes. Fees must be disclosed before the SME commits. | New **`billing` module** with versioned price books and an immutable fee ledger. Amounts are configuration. → [ADR-0002](../adr/0002-six-domain-modules.md), [ADR-0013](../adr/0013-billing-and-sme-charging.md) |
| G2 | **The money flow is undefined.** Gruber's "servicing fee for payment processing and collections" implies CredSort would handle loan repayments. | Holding or forwarding third-party funds is likely to make CredSort a regulated financial intermediary (to be confirmed by legal review). It also contradicts "CredSort never lends, needs no balance sheet" (canvas). | **CredSort stays out of the money flow** and invoices only its own fees. → [ADR-0014](../adr/0014-no-loan-money-flow.md) |
| G3 | **Authentication is not specified.** Only authorization is described. | Confidentiality is a driving characteristic. The offline-demo requirement also rules out depending on an external identity provider for the MVP. | Built-in session auth now, OIDC + MFA before the pilot. → [ADR-0016](../adr/0016-authentication.md) |
| G4 | **Tenant isolation is code-level only.** | One missing `WHERE organization_id = …` leaks a competitor's financials. | Mandatory scoped repositories, cross-tenant probe tests in CI, PostgreSQL row-level security before real data. → [ADR-0017](../adr/0017-tenant-isolation.md) |
| G5 | **Money rules are incomplete.** `Decimal` is mentioned, but currency, rounding and serialization are not. | Fees are invoiced and ratios drive assessments. Rounding drift is an integrity defect. | → [ADR-0015](../adr/0015-money-and-financial-calculations.md) |
| G6 | **Fiduciaries are the main acquisition channel** (canvas, brainstorming, Gruber) but sit at P2 with no data model. | The 20 % revenue share requires *referral attribution from the first SME onboarded*. It cannot be added retroactively. | Organization types, delegation and referral attribution are modelled now; the portal comes later. → [ADR-0019](../adr/0019-organization-types-and-delegation.md) |
| G7 | **KYC/KYB and fraud** (Gruber §4, margin note "outsource the KYC risk") are absent. | Adverse selection is the top credit risk raised in feedback. | KYB behind a port, a stub in the MVP, a vendor later; a pilot loan cap. → [ADR-0020](../adr/0020-kyb-outsourced-via-port.md) |
| G8 | **Neutrality is a USP** ("no lender can buy a better position") but is not enforced anywhere. | It must hold in the code, or it is a marketing claim. | Ranking is a pure function of lender criteria and permitted fields; matching code cannot see billing data. → [ADR-0021](../adr/0021-matching-neutrality.md) |
| G9 | **Benchmark data is "the moat, not the AI"**, but there is no retention or aggregation policy for offer data. | Without immutable, linked offer history the moat never accumulates. | → [ADR-0022](../adr/0022-offer-data-for-rate-benchmark.md) |
| G10 | **Notifications** ("offer available", Pro-tier refinancing alerts) have no mechanism, and there is deliberately no broker. | Side effects must not create hidden coupling or lost writes. | In-process domain events after commit; fee recording stays inside the transaction. → [ADR-0023](../adr/0023-in-process-domain-events.md) |
| G11 | **Frontend structure** is undecided: one or two apps, and whether to use a BFF. | It affects cookies, CORS, auth and duplication. | One Next.js app with portals as route groups and an `/api` proxy. → [ADR-0018](../adr/0018-single-nextjs-app-with-portals.md) |
| G12 | **Driving characteristics.** "Simplicity" was ranked top-3. | Simplicity is a constraint on *how* we build. The business keeps changing (pricing, data sources, channels), so **evolvability** is what the system itself must exhibit. | Re-ranked: Confidentiality, Data integrity, Evolvability; Feasibility kept as a hard constraint. → [ADR-0012](../adr/0012-driving-architecture-characteristics.md) |
| G13 | **Hosting and data residency** for a pilot are unspecified. | Real SME financials fall under the Swiss nFADP. | → [ADR-0024](../adr/0024-deployment-and-demo-modes.md) |
| G14 | **The margin note "can we use an SLM, it is cheaper?"** | API cost per loan is part of the unit economics (Gruber §6). | The `LanguageModel` port makes the model a configuration choice, evaluated by tests. → [ADR-0009](../adr/0009-ai-explains-deterministic-results.md) |

## Inconsistencies in the source documents (not architectural, but they need an owner)

| Topic | Conflict | Recommendation |
|---|---|---|
| Revenue model | Pitch deck: lender pays 0.75 % (min CHF 2,000, cap CHF 7,500), SME free. Seb: SME tiers Basic/Light/Pro. Gruber: SME success fee (2 % example) plus servicing fee. **Team, 2026-11-19: SMEs will be charged.** | `billing` supports every option as configuration. The team should still decide (a) the SME fee and its trigger and (b) whether the lender success fee remains. |
| Milestone numbering | The Architecture Plan uses M0–M8 (technical); the Master Plan uses M0–M10 (product). | Prefix them in tickets: **T-M3** (technical) vs **P-M3** (product). |
| Market size | 161,000 SMEs (a count) vs CHF 562B (loan volume) appear side by side. | Gruber §5: keep counts and CHF amounts separate on every slide. Not an architecture issue. |

## Outcome

- Architecture style confirmed with an explicit trade-off analysis → [05-architecture-style.md](05-architecture-style.md)
- Domains re-cut from five to **six modules** (`billing` added) → [03-domain-model.md](03-domain-model.md)
- Characteristics re-ranked → [04-architecture-characteristics.md](04-architecture-characteristics.md)
- 24 ADRs: 0001–0011 formalize the existing register; 0012–0024 are new → [../adr/README.md](../adr/README.md)
