# ADR-0020: KYB Outsourced Through a Plug-in in Identity; Stub in the MVP; Pilot Loan Cap

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0003](0003-plug-in-extension-points.md), [ADR-0019](0019-organization-types-and-delegation.md), [ADR-0027](0027-context-tokens-and-service-trust.md), [ADR-0014](0014-no-loan-money-flow.md) |

## Context

- Gruber §4 warns about **adverse selection and fraud** and recommends multi-step screening, admission criteria and a cap per loan in the pilot.
- Margin note: **"outsource the KYC risk to another company in the market"**.
- Lenders still perform their own KYC before contracting (CredSort is not in the money flow). CredSort must keep unverified organizations off the marketplace.

## Decision

1. A **`KybProvider` plug-in** in Identity verifies organizations (legal existence, UID, registered address, signatory) and yields `UNVERIFIED`, `PENDING`, `VERIFIED` or `REJECTED` with evidence references (documents stay with the vendor).
2. **MVP:** a stub plug-in verifies synthetic organizations; platform admins verify or reject manually. Lenders are always admin-verified.
3. The **KYB status is a context-token claim** and is published as `identity.organization.verification_changed`. Marketplace requires `VERIFIED` to publish (SME) and to match or offer (lender).
4. **Pilot loan cap:** a configurable maximum requested amount per application during the pilot (Marketplace configuration).
5. Credit-bureau data (Creditreform, CRIF, Dun & Bradstreet are listed partners) is a later input to Data Confidence via a `CreditBureauProvider` plug-in in Intelligence.
6. **Pilot:** a Swiss KYB/KYC vendor behind the same plug-in; evaluate the public UID register as a low-cost first check.

## Alternatives considered

| Option | Why not |
|---|---|
| Build KYB in-house | Commodity with regulatory nuance; the team suggested outsourcing |
| No verification in the MVP | The demo could not answer the fraud question raised in feedback |

## Consequences

**Positive**: a credible answer to fraud risk; vendor-agnostic; testable offline.
**Negative**: vendor cost per check enters unit economics; manual verification in the MVP.

## Compliance

Tests: an unverified SME cannot publish; an unverified lender cannot see matches; an amount above the cap → 422; plug-in contract tests.

## Revisit when

A vendor is selected; or lenders require KYC evidence packages from CredSort.
