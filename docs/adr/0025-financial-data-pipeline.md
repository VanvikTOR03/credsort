# ADR-0025: Pipes-and-Filters Pipeline from Imported Ledger to Assessment

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team (pipeline version changes need two approvals) |
| **Owner** | Financial Intelligence owner |
| **Related** | [ADR-0001](0001-architecture-style.md), [ADR-0005](0005-import-workers.md), [ADR-0010](0010-import-recovery-and-idempotency.md), [ADR-0015](0015-money-and-financial-calculations.md), [ADR-0023](0023-event-driven-integration.md) |

## Context

The way from raw accounting data to an assessment is a fixed sequence of transformations. Integrity requires that every result can be reproduced and explained; evolvability requires that individual steps (a new data source, a new mapping, a new scorecard) can change without touching the others.

## Decision

The financial data path is a **pipeline of pure, versioned filters**, spanning two services:

| Stage | Filter | Service | Version recorded | Output (immutable) |
|---|---|---|---|---|
| 1 | Fetch | Accounting (plug-in) | provider + API version | raw pages (transient, never stored beyond the job) |
| 2 | Normalize (anti-corruption) | Accounting | `normalizer_version` | canonical entries |
| 3 | Validate (accounting invariants) | Accounting | `validator_version` | ImportBatch or a validation failure |
| — | `accounting.import.completed` event + claim check | — | — | — |
| 4 | Map accounts → categories | Intelligence | `mapping_version` | FinancialSnapshot |
| 5 | Compute metrics | Intelligence | `formula_version` per metric | FinancialMetrics (with `UNAVAILABLE` flags) |
| 6 | Assess | Intelligence | `scorecard_version` | CreditAssessment with factor explanations |
| 6b | Data Confidence | Intelligence | `confidence_model_version` | Confidence result (separate from the assessment) |

Rules:
1. Each filter is a **pure function** of its input and its version; no hidden state, clock or network access.
2. Every output records the **versions of all upstream filters** (lineage). Same inputs + same versions → byte-identical outputs.
3. **Versions are immutable.** Changing a mapping, formula or scorecard creates a new version; old results stay reproducible.
4. Re-running a later stage with a new version (e.g. a new scorecard on an old snapshot) creates a **new** result and never overwrites the old one.
5. A stage failure records a typed failure result (e.g. "unbalanced ledger") and emits a failure event; the previous valid results stay current.
6. Stages 4–6 run in one Intelligence transaction (with inbox and outbox), so a snapshot never exists without its metrics and assessment.

## Alternatives considered

| Option | Why not |
|---|---|
| One monolithic "analyze" function | Steps cannot be versioned, tested or replaced independently |
| Recalculate on read | Results drift when rules change; not reproducible |
| All stages in one service | Raw ledger handling and scoring have different trust and fault profiles ([ADR-0002](0002-service-decomposition.md)) |

## Consequences

**Positive**: reproducible and explainable assessments; each filter testable in isolation; new data sources only affect stages 1–2.
**Negative**: version registry to manage; storage for historical results.

## Compliance

FF-I2 (reproducibility), FF-I1 (formula tests), a test that every output carries complete lineage, and a test that no filter performs I/O (dependency check).

## Revisit when

Scenario volume requires precomputation; or empirical (statistical) scorecards are introduced (they are new filter versions with their own validation).
