# ADR-0002: Six Domain Modules and Their Boundaries

| | |
|---|---|
| **Status** | Proposed — **updates** the "five modules" decision in Architecture Plan v1 §3 |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [03-domain-model.md](../architecture/03-domain-model.md), [ADR-0013](0013-billing-and-sme-charging.md), [ADR-0021](0021-matching-neutrality.md) |

## Context

Architecture Plan v1 defined five modules: `access`, `accounting`, `analysis`, `lending`, `advisory`. On 2026-11-19 the team decided that **SMEs will be charged** (amount and trigger TBD). Candidate models include Basic/Light/Pro tiers, an SME success fee, the earlier lender success fee and a fiduciary revenue share. None of the five modules is a natural owner:

- In `lending`, pricing churn would mix into the marketplace core, and it would be harder to prove that fees never influence ranking.
- In `access`, commercial rules would mix with identity and consent.

## Decision

We will have **six modules**:

| Module | Owns |
|---|---|
| `access` | Organizations, users, memberships, roles, authentication, authorization, DataDisclosure (consent), delegation, KYB status, audit |
| `accounting` | Data connections, adapters, import jobs, canonical ledger |
| `analysis` | Mapping, snapshots, metrics, scorecard, Data Confidence, deterministic scenarios |
| `lending` | Applications, publication, lender criteria, eligibility and ranking, offers, comparison, rate estimates |
| `advisory` | AI and template explanations (stateless in the MVP) |
| `billing` | Price books, fee rules, plans, entitlements, fee charges, referral shares |

**Dependency rules** (acyclic; a module calls only another module's `api.py`):

- `access` depends on nothing.
- `accounting` → `access`
- `analysis` → `access`, `accounting`
- `lending` → `access`, `analysis`, `billing` (quotes and charges), but **matching code never imports `billing`** ([ADR-0021](0021-matching-neutrality.md))
- `advisory` → `access`, `analysis`, `billing` (entitlement checks only)
- `billing` → `access`

Upstream modules learn about downstream facts only through domain events ([ADR-0023](0023-in-process-domain-events.md)).

Fiduciaries are **not** a seventh module: they are an organization type with delegation (`access`) and referral attribution (`billing`) ([ADR-0019](0019-organization-types-and-delegation.md)).

## Alternatives considered

| Option | Why not |
|---|---|
| Keep five modules; pricing inside `lending` | Mixes frequently changing pricing into the core marketplace; neutrality is harder to enforce. |
| Pricing inside `access` | Identity and commerce change for different reasons and at different rates. |
| Seventh `fiduciary` module now | Premature; the P2 portal reuses access and billing concepts. |
| Split `analysis` into profiling + assessment modules | They share snapshots and versions; kept as separate internal components with separate test suites instead. |

## Consequences

**Positive**
- Revenue-model changes stay inside `billing`.
- A clear place for entitlements (e.g. what-if analysis for Pro).
- Neutrality is enforceable with an import rule.

**Negative / trade-offs**
- One more schema, API surface and set of tests.
- `lending` gains a synchronous dependency on `billing` (fee quote and charge in the same transaction).

## Compliance

- import-linter `layers` contract, plus a `forbidden` contract `lending.domain.matching ↛ billing`.
- A cross-module import of anything other than `<module>.api` fails CI.

## Revisit when

A capability grows its own data and change rate (e.g. the fiduciary portal, benchmark analytics); or `billing` must be isolated for regulatory reasons.
