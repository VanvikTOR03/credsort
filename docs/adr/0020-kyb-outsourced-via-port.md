# ADR-0020: KYB/KYC Outsourced Through a Port; Stub in the MVP; Pilot Loan Cap

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0003](0003-ports-and-adapters.md), [ADR-0019](0019-organization-types-and-delegation.md), [ADR-0014](0014-no-loan-money-flow.md) |

## Context

- Gruber §4 warns about **adverse selection and fraud** (applicants who never intend to repay) and recommends multi-step screening (KYC, credit data, data from the fiduciary), clear admission criteria, and a cap per loan in the pilot.
- A margin note on the Business Model canvas: **"outsource the KYC risk to another company in the market"**.
- Lenders keep doing their own KYC before contracting (CredSort is not in the money flow, [ADR-0014](0014-no-loan-money-flow.md)). CredSort's job is to keep obviously fake or unverified organizations off the marketplace.

## Decision

1. A **`KybProvider` port** in `access` verifies an organization (legal existence, UID, registered address, signatory) and returns a status: `UNVERIFIED`, `PENDING`, `VERIFIED` or `REJECTED`, with evidence references.
2. **MVP:** a `StubKybAdapter` marks synthetic organizations `VERIFIED`; a platform admin can verify or reject manually (screen A1). Lenders are always verified by a platform admin.
3. **Publication requires a `VERIFIED` SME**; matching and offers require a `VERIFIED` lender.
4. **Pilot loan cap:** a configurable maximum requested amount per application during the pilot (lending configuration).
5. Credit-bureau data (Creditreform, CRIF, Dun & Bradstreet are listed as partners) is a **future input to Data Confidence**, added through a separate port when contracted.
6. **Pilot:** integrate a Swiss KYB/KYC vendor behind the same port; evaluate the public UID register as a low-cost first check.

## Alternatives considered

| Option | Why not |
|---|---|
| Build KYB in-house | A commodity with regulatory nuance; the margin note suggests outsourcing. |
| No verification in the MVP | The demo would not show how fraud risk is handled, which is a known pitch question (Gruber §4). |

## Consequences

**Positive**: a credible answer to the fraud question; vendor-agnostic; testable offline.
**Negative**: the real vendor cost per check enters the unit economics; manual admin verification in the MVP.

## Compliance

- Tests: an unverified SME cannot publish (409/403); an unverified lender cannot see matches; an amount above the pilot cap is rejected (422).
- Port contract tests for every KYB adapter.

## Revisit when

A vendor is selected; or lenders require CredSort to provide KYC evidence packages.
