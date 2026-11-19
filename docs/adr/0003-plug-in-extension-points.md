# ADR-0003: Plug-in (Microkernel) Extension Points at the Edges

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0001](0001-architecture-style.md), [ADR-0007](0007-resilience.md), [ADR-0009](0009-ai-explains-deterministic-results.md), [ADR-0013](0013-billing-and-sme-charging.md), [ADR-0020](0020-kyb-outsourced-via-port.md), [ADR-0025](0025-financial-data-pipeline.md) |

## Context

Evolvability and interoperability: providers will be added or swapped (Abacus, bLink, cheaper LLMs, a KYB vendor, an invoicing provider), and rule sets will change (mappings, scorecards, fee calculators). The demo must also run offline. External formats must never leak into the domain (anti-corruption).

## Decision

Each service exposes **plug-in ports** (Python protocols) for its external dependencies and replaceable rule sets. Plug-ins are selected by configuration per environment. External formats are translated inside the plug-in (an anti-corruption layer).

| Service | Port | Plug-ins now | Later |
|---|---|---|---|
| Accounting | `AccountingDataProvider` | bexio, synthetic | Abacus |
| Accounting | `BankDataProvider` | — | SIX bLink (P2) |
| Intelligence | Mapping rules, scorecards, industry rule packs | Versioned data, registered by version ID | Empirical scorecards |
| Intelligence | `CreditBureauProvider` | — | Creditreform / CRIF (input to Data Confidence) |
| Advisory | `LanguageModel` | LLM API, deterministic templates (offline fallback) | Self-hosted SLM |
| Identity | `KybProvider` | Stub (synthetic organizations) | Swiss KYB vendor |
| Billing | Fee calculators | Fixed, percent with min/cap | New trigger/calculation types |
| Billing | `PaymentProvider` | — (charges exported) | Invoicing with Swiss QR-bills (pilot) |
| Notification | `Channel` | In-app | Email |
| Marketplace | `RateEstimator` | Illustrative (V1) | Empirical (V2) |

Rules:
- A port exists only where a dependency is **external, unstable or replaceable**, or where an **offline fallback** is required.
- Every port has a **contract test suite** that all its plug-ins must pass.
- Only plug-in code may import vendor SDKs or call external hosts (egress allowlist per service).

## Alternatives considered

| Option | Why not |
|---|---|
| Call vendor APIs directly from domain code | Vendor formats leak into scoring; no offline demo; hard to test |
| Plug-ins for internal service calls too | Internal calls are governed by API contracts ([ADR-0006](0006-api-contracts.md)), not plug-ins |

## Consequences

**Positive**: providers are swappable through configuration; offline demos; cost optimization (e.g. an SLM).
**Negative**: plug-ins must track vendor API changes; contract suites must be maintained.

## Compliance

- Port contract tests in each service's CI.
- Architecture rule: vendor SDK imports only in `plugins/`.
- Deployment config lists the active plug-ins per environment; OFFLINE uses only local plug-ins.

## Revisit when

A port keeps a single plug-in with no fallback need (consider removing it), or a new external dependency appears (add a port).
