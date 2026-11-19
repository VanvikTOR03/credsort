# ADR-0009: AI Only Explains Deterministic Results; the Model Is Configuration

| | |
|---|---|
| **Status** | Proposed — formalizes Architecture Plan v1 §5.3 and adds model choice and evaluation |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0003](0003-ports-and-adapters.md), [ADR-0007](0007-external-api-resilience.md), [ADR-0013](0013-billing-and-sme-charging.md) |

## Context

The AI Advisor helps SMEs understand assessments and what-if scenarios. Language models can invent numbers. The Brainstorming notes state "the moat is the data, not the AI", and a margin note asks whether a cheaper **SLM** (small language model) could be used. AI cost per loan belongs in unit economics (Gruber §6).

## Decision

1. **Calculation is deterministic.** Ratios, scores and scenarios come from `analysis`. The model **never** calculates or modifies scores, makes lending decisions or promises approval.
2. **Inputs are aggregates only:** verified metrics, factors, scenario before/after values and flags. No raw journal entries, no counterparties' names, no personal data.
3. **Output is explanation only**, labelled "AI-generated explanation", with the snapshot and assessment versions referenced.
4. **The model is configuration** behind the `LanguageModel` port. Any model, including a small/cheap SLM, may be used **if it passes the advisory evaluation suite**.
5. **Fallback:** `TemplateAdapter` produces deterministic explanations offline or on failure ([ADR-0007](0007-external-api-resilience.md)).
6. **Caching:** an explanation is cached per (assessment version, language, model version) to control cost.
7. **Entitlements:** which advisory features an SME gets (e.g. what-if in Pro) is checked via `billing.api.has_entitlement` ([ADR-0013](0013-billing-and-sme-charging.md)).
8. Guardrails in the prompt: no advice to manipulate financial statements; no credit promises.

## Alternatives considered

| Option | Why not |
|---|---|
| LLM computes ratios or scenarios | Not reproducible; invented numbers; violates data integrity. |
| Send raw ledger for "better" answers | Confidentiality and cost; no need for explanation tasks. |
| Fix one provider in code | Blocks cost optimization (SLM) and offline mode. |

## Consequences

**Positive**: integrity is preserved; cost is controllable; the demo works without AI.
**Negative**: explanations are limited to what deterministic engines provide; an evaluation suite must be maintained.

## Compliance

- **"No invented numbers" test:** every number in an AI output must appear in the input context (tolerating formatting).
- The evaluation suite (fixed scenarios × expected key points) must pass before a model change.
- A test asserts that the payload sent to the adapter contains no journal entries or personal fields.

## Revisit when

A conversational assistant (P2) is built; or a cheaper model fails the evaluation suite; or real data enter the system (review the provider's data-processing terms and region).
