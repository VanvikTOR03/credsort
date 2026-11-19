# ADR-0009: AI Only Explains Deterministic Results; Advisory Has No Data Access

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0002](0002-service-decomposition.md), [ADR-0003](0003-plug-in-extension-points.md), [ADR-0007](0007-resilience.md), [ADR-0013](0013-billing-and-sme-charging.md) |

## Context

The AI Advisor helps SMEs understand assessments and what-if scenarios. Language models can invent numbers. "The moat is the data, not the AI" (Brainstorming), and a margin note asks whether a cheaper SLM could be used. AI cost per loan belongs in unit economics (Gruber §6).

## Decision

1. **Calculation is deterministic** and happens in Financial Intelligence. The model **never** calculates or changes scores, makes lending decisions or promises approval.
2. **Advisory is a separate service with no database access to financial data.** It obtains **aggregates only** from Intelligence's `advisory-context` internal API, on behalf of the requesting user.
3. Inputs exclude journal entries, counterparties' names and personal data.
4. Output is labelled "AI-generated explanation" and references the assessment or scenario version and the model version.
5. **The model is a plug-in** (`LanguageModel`). Any model, including a small/cheap or self-hosted SLM, may be used **if it passes the advisory evaluation suite**.
6. **Fallback:** the template plug-in produces deterministic explanations offline or on failure.
7. Explanations are cached per (assessment/scenario version, language, model version).
8. Feature access (e.g. what-if for Pro) uses Billing entitlements (event-fed cache).
9. Prompt guardrails: no advice to manipulate financial statements, no credit promises.

## Alternatives considered

| Option | Why not |
|---|---|
| LLM computes ratios or scenarios | Not reproducible; invented numbers |
| Advisory inside Intelligence | The LLM integration would sit next to the largest store of financial data |
| Send raw ledgers for "better" answers | Confidentiality and cost, with no need for explanation tasks |

## Consequences

**Positive**: integrity is preserved; a compromised or misbehaving AI component cannot read financial databases; cost is controllable.
**Negative**: explanations are limited to deterministic outputs; an evaluation suite must be maintained.

## Compliance

- FF-F4: every number in an AI output appears in its input context.
- FF-C8: Advisory has no credentials for financial databases; its egress allowlist contains only the configured model endpoint.
- The evaluation suite must pass before a model change.

## Revisit when

A conversational assistant (P2) is built; or real data enter the system (verify provider terms and region).
