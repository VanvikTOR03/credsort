# 07 — Failure Modes and Risks: Where This Architecture Can Break

**Date:** 2026-11-19 · **Status:** Proposed

This is a failure-mode analysis of the chosen architecture ([05](05-architecture-style.md)). For each way it can break we list the effect, how we **detect** it, the **design response**, and the **residual risk** we accept. Severity reflects the impact on the driving characteristics: confidentiality, integrity, evolvability.

| Severity | Meaning |
|---|---|
| **High** | Violates confidentiality or integrity, or stops core journeys |
| **Medium** | Delays or degrades a journey; recoverable without data loss |
| **Low** | Cosmetic or easily recovered |

## 1. Data integrity

| ID | Scenario | What breaks | Sev. | Detection | Design response | Residual |
|---|---|---|---|---|---|---|
| R-I1 | Outbox relay stops (crash, bug) | Fees, snapshots, notifications and audit records are delayed | Medium | Outbox-lag alert (> 1 min) | Relay is stateless and restartable; events are durable in the outbox until confirmed | Delay only |
| R-I2 | Broker node fails right after accepting a message | An event could be lost | High | Reconciliation jobs | Quorum queues; the relay marks an event sent **only after publisher confirm**; replay from the outbox | Very low |
| R-I3 | Duplicate delivery (at-least-once) | Double charge, double snapshot | High | FF-I4 duplicate-delivery test | Inbox `(consumer, event_id)` unique; charge unique per `quote_id`; snapshot unique per `(batch, mapping_version)` | None (DB-enforced) |
| R-I4 | Events arrive out of order (e.g. *suspended* after *reinstated*) | Stale projections | Medium | Version check metrics | `credsortaggregateversion`; consumers ignore older versions | Low |
| R-I5 | Poison message (cannot be processed) | One consumer stalls on one item | Medium | DLQ depth > 0 alert | Bounded retries → DLQ; the queue keeps flowing; replay tool after the fix | Item delayed until fixed |
| R-I6 | Price book changes or quote expires between display and action | Fee charged differs from fee shown | High | FF-I5; `billing.charge.held` alert | Fee-bearing actions require a valid **signed** quote; the charge equals the quote; expired → the UI re-quotes and the payer re-confirms; Billing verifies each quote exists and is unused | Payer may need to re-confirm |
| R-I7 | Two SME users select different offers at the same time | Two selected offers | High | FF-I3 concurrency test | Row lock + partial unique index in Marketplace; the loser gets 409 | None |
| R-I8 | **One service database is restored to an earlier point** (e.g. Billing) | Charges missing for existing selections; or selections missing for existing charges | High | Reconciliation after restore | Restore runbook: restore → replay upstream outboxes since the restore point → reconcile → review "orphans" (reverse via reversal entries) → reopen traffic. Outboxes retained ≥ 35 days. | Medium: depends on runbook discipline |
| R-I9 | A mapping rule or scorecard is edited in place | Old assessments no longer reproducible | High | FF-I2 reproducibility test | Pipeline versions are immutable; a change creates a new version ID | None |
| R-I10 | Intelligence fetches a ledger that was deleted in between (deletion request) | Pipeline step fails | Low | Assessment-failed event | Claim-check API returns 410; Intelligence records a failure, no snapshot | None |
| R-I11 | A newer assessment appears between the SME's preview and confirmation | Lenders see different data than previewed | High | — | Publication is bound to the **assessment ID shown in the preview**; the extract of an immutable assessment is identical | None |
| R-I12 | Clock skew between services | Wrong quote expiry or ordering decisions | Low | Time-drift monitoring | Expiry checked against Billing-signed `exp` with tolerance; ordering uses aggregate versions, never timestamps | Low |
| R-I13 | A developer publishes to the broker directly inside a handler (dual write) | Lost or phantom events | High | Architecture test | The shared outbox library is the only publishing API; direct broker client use outside the relay fails CI | Low |
| R-I14 | Central audit lags or misses records | The SME's activity log is incomplete | Medium | Daily local-vs-central count reconciliation; hash-chain check | Local audit is written in the business transaction (source of truth) and forwarded via the outbox | Delay only |

## 2. Confidentiality

| ID | Scenario | What breaks | Sev. | Detection | Design response | Residual |
|---|---|---|---|---|---|---|
| R-C1 | XSS or CSRF in the web app | Session misuse | High | Security tests, CSP reports | No tokens in the browser; HttpOnly cookies; CSP; CSRF protection on the BFF; MFA | Low |
| R-C2 | Context token leaks inside the network (e.g. a log) | Replay for up to about 2 minutes | High | FF-C6 sentinel test | Tokens never logged; audience restriction; short lifetime; mTLS in the pilot | Low |
| R-C3 | A member is removed but still holds a valid token | Access continues briefly | Medium | — | Identity stops issuing at once; services deny-list on `membership.revoked` | Window ≤ event latency (worst case about 2 min) |
| R-C4 | A gateway misroute exposes `/internal/*` | Any user could call internal APIs | High | FF-C4 network test | Internal APIs also require a **service identity token** from an allowed caller; gateway route allowlist | Low (two independent controls) |
| R-C5 | One service is compromised | Attacker pivots to other data | High | Anomaly alerts, audit | Least privilege: own DB only, egress allowlists, network policies, callee allow-lists; Advisory has no financial DB access | Medium if Intelligence or Marketplace is compromised (they hold C4/C3); separate DB instances limit the blast radius |
| R-C6 | A lender infers values by repeatedly adjusting criteria thresholds | Leakage of values | Medium | Audit of criteria changes | Only **permitted** fields can be used (the SME consented to their use); criteria changes rate-limited and audited; optional value bands | Accepted for permitted fields |
| R-C7 | Sensitive data ends up in events, outboxes or DLQs | Copies outside the owner | High | FF-C5 schema scan | Thin events; claim check; DLQ access restricted | Low |
| R-C8 | Sensitive data in logs or traces | Leakage to the observability stack | High | FF-C6 | Allowlist logging; no bodies in spans | Low |
| R-C9 | A new query forgets the tenant filter | Cross-tenant read | High | FF-C1 probe suite | Row-level security on every tenant table + probe tests | Low |
| R-C10 | A fiduciary acts beyond its delegation | Unauthorized actions | Medium | Audit (`on_behalf_of`) | Delegation scopes in the context token; delegation never includes selection or disclosure | Low |
| R-C11 | The LLM provider retains prompts | Third-party exposure | Medium | Provider review | Aggregates only; DPA and region check; self-hosted SLM or templates possible | Medium until provider terms are verified |
| R-C12 | A disclosure is revoked after the lender exported data | Data cannot be recalled | Medium | Audit | UI warning before granting; contractual terms with lenders | Accepted |
| R-C13 | Backups are stolen | Bulk disclosure | High | Access monitoring | Encrypted backups; KMS-controlled keys; restricted access | Low |

## 3. Availability and fault tolerance

| ID | Scenario | What breaks | Sev. | Detection | Design response | Residual |
|---|---|---|---|---|---|---|
| R-A1 | **Identity or Keycloak is down** | No logins and no new context tokens; all journeys stop once tokens expire (about 2 min) | High | Health checks, issuance-error alerts | ≥ 3 replicas, own database, cached JWKS, tokens valid until expiry | **Single critical dependency, accepted** |
| R-A2 | RabbitMQ is down | Synchronous journeys continue; fees, snapshots, notifications and audit are delayed | Medium | Outbox-lag alert | Quorum cluster; events wait safely in outboxes | Delay only |
| R-A3 | Billing is down | New quotes unavailable → fee-bearing actions blocked unless a valid cached quote exists | Medium | Circuit-breaker alert | Quotes fetched when screens load and cached until expiry (e.g. 24 h); ≥ 2 replicas; **fail closed** by design | Accepted (never charge an undisclosed fee) |
| R-A4 | Intelligence is down | Dashboards, assessments and new publications unavailable; matching and offers continue on published profiles | Medium | Health checks | Marketplace never needs Intelligence for matching; clear error on publication | Medium |
| R-A5 | bexio or Accounting is down | Imports fail; the last snapshot remains | Low | Import-failure alert | Bounded retries; synthetic path unaffected | Low |
| R-A6 | Advisory or the LLM is down | No AI explanations | Low | Circuit breaker | Template plug-in fallback | Low |
| R-A7 | Marketplace database is down | Core marketplace unavailable | High | Health checks | Managed HA PostgreSQL with failover | Accepted (the core must be strongly consistent) |
| R-A8 | A slow upstream causes cascading latency | Timeouts pile up | Medium | Latency alerts | Timeouts, circuit breakers, separate connection pools per upstream (bulkheads), two-hop limit | Low |
| R-A9 | Import storm (many SMEs at once) | Workers saturated; slow imports | Low | Queue depth | Separate worker deployment; per-organization quotas; fair scheduling | Low |
| R-A10 | Signing-key rotation mistake | Every context token rejected | High | Issuance and 401 spike alerts | Rotation runbook with JWKS overlap ≥ 24 h; staged rollout | Low |

## 4. Evolvability and operability

| ID | Scenario | What breaks | Sev. | Detection | Design response | Residual |
|---|---|---|---|---|---|---|
| R-E1 | **Drift into a distributed monolith** (more and more sync calls) | Coupled deployments, cascading failures | High | FF-E6 static dependency check | Closed call inventory ([06 §2](06-runtime-and-integration.md)); a new sync dependency requires an ADR | Low |
| R-E2 | A breaking API or event change is deployed | Consumers fail | High | FF-E3/FF-E4 contract and schema checks | Additive changes only; `v2` published alongside `v1` | Low |
| R-E3 | A shared library grows domain logic | Hidden coupling between services | Medium | FF-E7 review rule | Libraries limited to technical concerns ([ADR-0030](../adr/0030-repository-and-shared-libraries.md)) | Low |
| R-E4 | A projection silently drifts (entitlements, deny-list) | Wrong feature access | Medium | Reconciliation, startup rebuild | Versioned projections; rebuild from source on startup | Low |
| R-E5 | Hard-to-debug cross-service flows | Slow incident resolution | Medium | — | End-to-end tracing across HTTP and messages | Low |
| R-E6 | Heavy local stack (many containers) | Slower development; demo risk | Low | — | Compose profiles; offline profile tested in CI; demo rehearsal | Low |
| R-E7 | Database migrations force lockstep deploys | Loss of independent deployment | Medium | Pipeline checks | Expand → migrate → contract; no shared tables | Low |

## 5. Data lifecycle and compliance

| ID | Scenario | What breaks | Sev. | Detection | Design response | Residual |
|---|---|---|---|---|---|---|
| R-D1 | A deletion request is executed only partly (one service fails) | Personal or financial data remains | High | Deletion tracking with per-service confirmations; overdue alert | Retries; Identity closes the request only when all services confirm ([ADR-0031](../adr/0031-data-lifecycle-and-deletion.md)) | Medium until all confirm |
| R-D2 | Benchmark retention conflicts with the right to deletion | Legal exposure | Medium | Legal review | Offers are **anonymized** (organization links removed), not kept identifiable | Pending legal review |
| R-D3 | **Event replay re-creates data of a deleted organization** | Deleted data reappears | High | Replay tests | Consumers check a tombstone list of deleted organizations before applying events; outbox rows of deleted organizations are purged | Low |
| R-D4 | A provider processes data outside Switzerland/EU | Residency breach | Medium | Provider checklist | Allowed-provider list per environment; DPA required before real data | Low after review |

## 6. Business-model changes

| ID | Scenario | Effect on the architecture | Response |
|---|---|---|---|
| R-B1 | The SME fee needs a new trigger (e.g. "subscription credit applied on success") | New trigger type + calculator plug-in | Billing change only; one new event field at most |
| R-B2 | The business wants servicing or payment flows | CredSort would enter the money flow | Blocked by [ADR-0014](../adr/0014-no-loan-money-flow.md); requires legal review and a licensed partner |
| R-B3 | The lender fee is dropped or kept | Configuration only | Activate a new price book |

## 7. Single points of failure

| Component | Why it is critical | Accepted? | Mitigation |
|---|---|---|---|
| Identity + Keycloak | Every request needs a valid context token | **Yes** (central authorization is a confidentiality feature) | HA replicas, cached keys, token lifetime as a buffer |
| Marketplace database | The strongly consistent core | **Yes** | Managed HA failover, PITR |
| Edge gateway | Single entry point | **Yes** | Managed, redundant load balancer |
| RabbitMQ | Event transport | Not a hard SPOF (outboxes buffer) | Quorum cluster |

## 8. Fault-injection tests to run before the pilot

1. Kill the outbox relay of each service during load → no event lost after restart.
2. Kill a RabbitMQ node during publishing → no event lost (publisher confirms + quorum).
3. Deliver every event twice and out of order → no duplicate effects, no stale state.
4. Billing down during publish and select → actions blocked unless a valid quote exists; no charge without a quote.
5. Intelligence down → matching and offers continue; publication blocked with a clear message.
6. Identity down for 5 minutes → existing tokens work until expiry, then a clean re-login path.
7. bexio returns 429/503/timeouts → bounded retries, failed job, previous snapshot intact.
8. LLM timeouts → template explanations.
9. Restore Billing's database to one hour earlier → runbook restores consistency with zero unexplained mismatches.
10. Organization deletion followed by replay of all events → no data of the deleted organization reappears.

## 9. Residual risks accepted (summary)

| Risk | Why accepted |
|---|---|
| Identity is a shared critical dependency (R-A1) | Centralized authorization is essential for confidentiality; mitigated by HA |
| Fee-bearing actions fail closed without a valid quote (R-A3) | Integrity and transparency outrank availability |
| Revocation window of up to about 2 minutes (R-C3) | Bounded by token lifetime; deny-list usually closes it in seconds |
| Values of permitted fields can be inferred by a lender (R-C6) | The SME consented to their use |
| Data already received by a lender cannot be recalled (R-C12) | Inherent to disclosure; communicated to the SME |
| Restore of one database needs a careful runbook (R-I8) | Inherent to a database per service; outbox retention makes it recoverable |
