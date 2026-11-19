# ADR-0028: Local Audit in Every Service plus a Central, Tamper-Evident Audit Log

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | To assign |
| **Related** | [ADR-0011](0011-consistency-model.md), [ADR-0023](0023-event-driven-integration.md), [08](../architecture/08-security-and-data-protection.md) |

## Context

SMEs should see who used their data (screen S12); disputes ("I never selected that offer") need evidence; regulators and lenders will ask for traceability. In a service-based design, actions happen in many services.

## Decision

1. Every service writes an **AuditRecord** for critical actions **in the same transaction** as the action: imports, assessments, publication, disclosure grants and revocations, lender reads of profiles, offers, selections, quotes and charges, delegation and membership changes, admin actions.
2. AuditRecords contain actor, acting organization, represented organization (delegation), action, resource reference, time and request/trace ID, and **never** financial values or personal details beyond IDs.
3. Records are forwarded through the outbox as `<service>.audit.recorded` events to the **Audit service**, which stores them **append-only** and **hash-chained** per organization stream.
4. The SME activity view and admin audit queries read from the Audit service (scoped by organization).
5. Local audit tables remain the source of truth; daily reconciliation compares counts per service and verifies the hash chains.
6. Retention: as required by legal review (default proposal: 10 years for actions related to charges, otherwise per the data lifecycle policy, [ADR-0031](0031-data-lifecycle-and-deletion.md)).

## Alternatives considered

| Option | Why not |
|---|---|
| Only local audit tables | No cross-service activity view; each service needs its own query API |
| Only a central audit service called synchronously | Audit writes would depend on another service's availability; not atomic with the action |
| Logging as audit | Logs are not complete, not tamper-evident and must not contain business details |

## Consequences

**Positive**: atomic local evidence plus a complete, tamper-evident global history.
**Negative**: duplicated storage of audit records; the central log lags by seconds.

## Compliance

FF-I6 (local vs central reconciliation), FF-I7 (hash-chain verification), and a test that every critical use case writes an AuditRecord in its transaction.

## Revisit when

External auditors require a qualified timestamping or WORM storage service.
