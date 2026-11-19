# ADR-0003: Ports & Adapters for External Systems Only

| | |
|---|---|
| **Status** | Proposed — extends Architecture Plan v1 §3.1 |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0007](0007-external-api-resilience.md), [ADR-0009](0009-ai-explains-deterministic-results.md), [ADR-0013](0013-billing-and-sme-charging.md), [ADR-0020](0020-kyb-outsourced-via-port.md) |

## Context

External dependencies are unstable or unavailable offline: bexio (data availability unverified), an LLM provider (cost, availability), a future KYB vendor, and a future invoicing/payment provider. Abacus and SIX bLink are planned (P2). Internal module calls do not need this indirection.

## Decision

We will define a **port** (a Python protocol in the owning module's `ports/`) only where an external dependency is unstable, replaceable, or needs an offline fallback. Adapters live in `adapters/` and translate external formats into CredSort's model (an **anti-corruption layer**). External formats never leave the adapter.

| Port | Module | MVP adapters | Later |
|---|---|---|---|
| `AccountingDataProvider` | accounting | `BexioAdapter`, `SyntheticDataAdapter` | `AbacusAdapter` |
| `LanguageModel` | advisory | `LlmApiAdapter`, `TemplateAdapter` (offline fallback) | Smaller/cheaper models via configuration |
| `KybProvider` | access | `StubKybAdapter` | Swiss KYB vendor ([ADR-0020](0020-kyb-outsourced-via-port.md)) |
| `PaymentProvider` | billing | *none* (charges recorded, invoicing manual/export) | Invoicing / payment service ([ADR-0013](0013-billing-and-sme-charging.md)) |
| `Notifier` | shared | `InAppNotifier` | Email adapter |

A `BankDataProvider` port for bLink is added **when P2 work starts**, not before.

Module-to-module calls use public `api.py` facades and DTOs, **not** ports.

## Alternatives considered

| Option | Why not |
|---|---|
| Call external SDKs directly from use cases | bexio payloads would leak into scoring; no offline demo; hard to test. |
| A port for every dependency, including internal modules | Boilerplate without benefit; slows a two-person team. |

## Consequences

**Positive**: the offline demo works; bexio problems never block the MVP; providers can be swapped (e.g. a cheaper LLM).
**Negative**: adapters must be kept in sync with vendor API changes; contract tests are needed per adapter.

## Compliance

- Each port has a contract test suite that every adapter must pass (e.g. both accounting adapters return valid canonical ledgers for the same fixture).
- import-linter: only `*/adapters/*` may import vendor SDKs or HTTP clients for external APIs.

## Revisit when

A new external dependency appears (add a port) or a port has had a single adapter for a long time and no fallback need (consider removing it).
