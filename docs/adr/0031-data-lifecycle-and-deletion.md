# ADR-0031: Data Lifecycle — Retention, Deletion and Anonymization Across Services

| | |
|---|---|
| **Status** | Proposed (retention periods subject to legal review) |
| **Date** | 2026-11-19 |
| **Deciders** | CredSort team |
| **Owner** | Identity owner (coordination) |
| **Related** | [ADR-0004](0004-database-per-service.md), [ADR-0022](0022-offer-data-for-rate-benchmark.md), [ADR-0023](0023-event-driven-integration.md), [ADR-0028](0028-central-audit-log.md), [08 §9](../architecture/08-security-and-data-protection.md) |

## Context

Personal and company data are spread over several service databases, outboxes, backups and caches. The Swiss nFADP grants rights such as deletion. The benchmark needs historical offers, and audit and accounting rules may require retention. Event replay could bring deleted data back.

## Decision

1. **Deletion is coordinated by Identity.** A deletion request (organization or user) is recorded and published as `identity.organization.deletion_requested`.
2. Each data-holding service applies its **lifecycle rule** and confirms completion via an audit event:

| Service | Action |
|---|---|
| Accounting | Delete ledger, batches and connections; revoke and delete bexio tokens |
| Intelligence | Delete snapshots, metrics, assessments and scenarios |
| Marketplace | Delete applications, disclosures and profiles; **anonymize** offers for the benchmark (remove organization references) |
| Billing | Keep charges and invoices for the legal retention period (accounting law), then delete; anonymize referral data |
| Advisory | Purge cached explanations |
| Notification | Delete notifications |
| Audit | Keep records for the audit retention period, with personal fields pseudonymized |
| Identity | Delete users and organization after all services confirm; keep a **tombstone** (ID + deletion time) |

3. Identity **tracks per-service confirmation** and alerts on overdue completion. The request closes only when every service has confirmed.
4. **Tombstones** prevent resurrection: consumers check the tombstone list before applying events, and the replay tool skips tombstoned organizations ([07](../architecture/07-failure-modes-and-risks.md) R-D3).
5. **Outbox rows** of deleted organizations are purged after delivery; backups expire on their normal rotation (documented as a known delay).
6. Default retention proposals (to be confirmed by legal review): ledger data while the connection is active plus 12 months; inactive organizations deleted after 24 months of inactivity with notice.

## Alternatives considered

| Option | Why not |
|---|---|
| Delete everything immediately everywhere | Conflicts with accounting retention for invoices and with audit evidence |
| Soft delete only | Not compliant with deletion rights for personal data |
| Crypto-shredding per organization | Strong option for the future; adds key management per tenant now |

## Consequences

**Positive**: deletion rights can be honoured across a distributed system; the benchmark survives through anonymization.
**Negative**: deletion is eventually complete, not instantaneous; backups retain data until rotation.

## Compliance

- End-to-end test: deletion request → all services confirm → no data for the organization remains except retained, documented records.
- Replay test: replaying all events after deletion does not recreate data (FF for R-D3).

## Revisit when

Legal review sets retention periods; or per-tenant encryption keys (crypto-shredding) become feasible.
