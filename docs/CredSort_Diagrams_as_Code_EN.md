# CredSort — Diagrams as Code

**Status:** Proposed diagram pack for Architecture Baseline & Master Product Plan v1.0  
**Format:** Mermaid in Markdown (`.md`) plus standalone `.mmd` source files  
**Language:** English (aligned with the existing plans)  
**Scope:** Swiss SME credit marketplace MVP. Real bank lending and empirically validated credit ratings are **not** implemented in the demo.

> These are **design diagrams**, not reverse-engineered diagrams of a deployed application. They describe agreed target behavior and assumptions to verify during development. They are based on `CredSort_Architecture_Implementation_Plan_EN_v1.md` and `CredSort_Master_Product_Development_Plan_EN_v1.md`.

## Diagram index

| No. | Diagram | Purpose |
|---|---|---|
| 01 | [System Context](#01-system-context) | Who interacts with CredSort and which external systems it uses. |
| 02 | [Containers and Deployment](#02-containers-and-deployment) | One logical backend, one relational database, and two outside API providers. |
| 03 | [Backend Modules and Public Interfaces](#03-backend-modules-and-public-interfaces) | Module dependency direction: consumers call owner api.py; owned database schemas are not accessed by other modules. |
| 04 | [Financial Data Lineage and Separation of Scores](#04-financial-data-lineage-and-separation-of-scores) | Canonical accounting flow, immutable data provenance, and distinct assessment/matching outputs. |
| 05 | [Sequence — bexio Connection, Import and Assessment](#05-sequence--bexio-connection-import-and-assessment) | End-to-end asynchronous import, 202 + polling, reproducible snapshot, and the manual retry path. |
| 06 | [Sequence — Consent, Lender Matching and Offer Selection](#06-sequence--consent-lender-matching-and-offer-selection) | Privacy-safe discovery and transactional selection of an immutable loan offer. |
| 07 | [Sequence — AI Advice and Deterministic What-if](#07-sequence--ai-advice-and-deterministic-what-if) | Calculations remain deterministic, while the LLM only explains permitted aggregate results. |
| 08 | [Entity Relationships — Accounting and Analysis](#08-entity-relationships--accounting-and-analysis) | Conceptual model of the versioned data pipeline; primary and foreign key names are illustrative. |
| 09 | [Entity Relationships — Access and Lending](#09-entity-relationships--access-and-lending) | Conceptual model for organizations, publication permissions, applications, immutable offers and audit records. |
| 10 | [State Machine — Accounting Import Job](#10-state-machine--accounting-import-job) | Manual retry creates a new job; unfinished jobs are failed on single-process startup. |
| 11 | [State Machine — Loan Application](#11-state-machine--loan-application) | Offers-received is a derived UI state, not a stored application status. |
| 12 | [State Machine — Loan Offer](#12-state-machine--loan-offer) | Immutable offer terms; only an authorized SME can select; at most one SELECTED per application. |
| 13 | [Privacy Decision Flow — Matching Eligibility](#13-privacy-decision-flow--matching-eligibility) | Prevents indirect disclosure through filters, ranking, results, and counts. |
| 14 | [Master Product Roadmap and Dependencies](#14-master-product-roadmap-and-dependencies) | Product milestones; validation can run in parallel with implementation. |

## Design conventions and constraints

- **Financial Assessment ≠ Data Confidence ≠ Lender Match ranking.** Scoring is demonstrative, not a validated probability of default.
- **Connecting bexio ≠ consent to disclose.** Discovery requires published applications and per-field matching permissions.
- **One Modular Monolith:** five modules (`access`, `accounting`, `analysis`, `lending`, `advisory`), one FastAPI process and one PostgreSQL instance for the initial architecture; no message broker.
- **Portals:** Next.js SME Portal and Lender Portal; bexio is an external accounting system, not the bank platform.
- **Data lineage:** immutable, versioned imports/snapshots/assessments. Loan offers retain immutable terms after submission.
- **Assumptions:** OAuth callback shape, bexio data availability, rate benchmark inputs, and any real bank integration need empirical verification.
- **Sequence semantics:** the arrows represent logical calls. Real implementation must define precise FastAPI routes, transaction scopes and errors.

## 01. System Context

Who interacts with CredSort and which external systems it uses.

```mermaid
flowchart LR
  SME["Swiss SME representatives"]
  LENDER["Banks and other lenders"]
  FID["Fiduciaries / Treuhänder (future)"]
  PLATFORM["CredSort — SME lending marketplace"]
  BEXIO["bexio — accounting data / OAuth"]
  AI["External LLM provider — explanations only"]

  SME <-->|"Profile, application, offers"| PLATFORM
  LENDER <-->|"Criteria, matching, offers"| PLATFORM
  FID -.->|"Future delegated client support"| PLATFORM
  PLATFORM <-->|"Consented accounting import"| BEXIO
  PLATFORM <-->|"Minimal aggregate inputs / advisory output"| AI
```

## 02. Containers and Deployment

One logical backend, one relational database, and two outside API providers.

```mermaid
flowchart TB
  U1["SME browser"]
  U2["Lender browser"]
  subgraph LOCAL["CredSort deployment — Docker Compose"]
    FE["Frontend container — Next.js / TypeScript"]
    BE["Backend container — FastAPI modular monolith"]
    DB[("PostgreSQL — schemas owned by modules")]
    FE -->|"HTTPS / JSON — browser calls"| BE
    BE -->|"SQLAlchemy / transactions"| DB
  end
  BX["bexio OAuth & accounting REST API"]
  LLM["External LLM API (optional)"]
  U1 --> FE
  U2 --> FE
  BE -->|"OAuth exchange; read data; retries"| BX
  BE -->|"Aggregates only; timeout; fallback"| LLM
  NOTE["Import job initially runs in backend process; no queue broker or Redis"]
  NOTE -.-> BE
```

## 03. Backend Modules and Public Interfaces

Module dependency direction: consumers call owner api.py; owned database schemas are not accessed by other modules.

```mermaid
flowchart TB
  HTTP["FastAPI entry points / application orchestration"]
  subgraph MONO["CredSort Modular Monolith"]
    ACCESS["access — identity, consent, authorization, audit"]
    ACC["accounting — connections, canonical ledger, import jobs"]
    ANA["analysis — snapshots, ratios, scorecard, confidence, scenarios"]
    LEND["lending — applications, matching, offers, benchmark"]
    ADV["advisory — AI explanation / template fallback"]
  end
  HTTP --> ACCESS
  HTTP --> ACC
  HTTP --> ANA
  HTTP --> LEND
  HTTP --> ADV
  ANA -->|"accounting.api — validated entries"| ACC
  LEND -->|"analysis.api — approved profile/assessment"| ANA
  ADV -->|"analysis.api — metrics and what-if results"| ANA
  ACC -.->|"access.api — authorize"| ACCESS
  ANA -.->|"access.api — authorize"| ACCESS
  LEND -.->|"access.api — consent and audit"| ACCESS
  ADV -.->|"access.api — authorize"| ACCESS
  P1[("access schema")]
  P2[("accounting schema")]
  P3[("analysis schema")]
  P4[("lending schema")]
  ACCESS --> P1
  ACC --> P2
  ANA --> P3
  LEND --> P4
```

## 04. Financial Data Lineage and Separation of Scores

Canonical accounting flow, immutable data provenance, and distinct assessment/matching outputs.

```mermaid
flowchart LR
  B["bexio API"]
  S["Synthetic Data Adapter"]
  CAN["Validated canonical accounting entries"]
  MAP["Account mapping + mapping version"]
  SNAP["Immutable FinancialSnapshot"]
  MET["FinancialMetric — formula version + quality flags"]
  ASSESS["Financial Assessment — scorecard version"]
  CONF["Data Confidence — completeness / freshness"]
  APP["Published loan application with disclosure"]
  MATCH["Lender-specific eligibility + match ranking"]
  RATE["Illustrative rate range — assumptions + source"]
  AI["AI explanations — no score mutation"]

  B --> CAN
  S --> CAN
  CAN --> MAP --> SNAP --> MET
  MET --> ASSESS
  MET --> CONF
  ASSESS --> APP
  CONF --> APP
  APP -->|"Authorized fields only"| MATCH
  APP -.-> RATE
  MET --> AI
  ASSESS --> AI
  CONF --> AI
  NOTE["Credit score is not a bank rating or probability of default"]
  NOTE -.-> ASSESS
```

## 05. Sequence — bexio Connection, Import and Assessment

End-to-end asynchronous import, 202 + polling, reproducible snapshot, and the manual retry path.

```mermaid
sequenceDiagram
  autonumber
  actor SME
  participant UI as SME Portal
  participant API as FastAPI / access
  participant ACC as accounting ImportService
  participant BX as bexio OAuth / API
  participant DB as PostgreSQL
  participant ANA as analysis

  SME->>UI: Connect bexio account
  UI->>API: Request bexio authorization
  API-->>UI: Redirect to bexio authorization endpoint
  UI->>BX: User authorization (browser redirect)
  BX-->>API: Authorization callback / code
  API->>BX: Exchange code for credentials
  BX-->>API: Scoped access / refresh tokens
  API->>DB: Store encrypted connection credentials
  API-->>UI: Connection active

  SME->>UI: Import accounting data
  UI->>API: POST /companies/{id}/import-jobs
  API->>API: Verify SME membership / permissions
  API->>DB: Create PENDING ImportJob
  API->>ACC: Schedule job in backend process
  API-->>UI: 202 Accepted + job URL

  ACC->>DB: Mark job RUNNING
  loop Each paginated bexio response
    ACC->>BX: Fetch permitted accounting data
    alt Response 429 / transient 5xx
      BX-->>ACC: Retry-After / error
      ACC->>ACC: Bounded retry / backoff
    else Response 401 / 403
      BX-->>ACC: Authorization error
      ACC->>DB: Mark FAILED; reconnect needed
    else Response successful
      BX-->>ACC: Account / journal payloads
    end
  end
  opt Import data is complete and valid
    ACC->>ACC: Normalize, reconcile, content hash
    ACC->>DB: Atomic insert ImportBatch + canonical entries
    ACC->>ANA: Create versioned snapshot from validated import
    ANA->>DB: Persist snapshot and metrics + provenance
    ACC->>DB: Mark job COMPLETED
  end
  loop Until terminal status
    UI->>API: GET /import-jobs/{id}
    API->>DB: Read status
    API-->>UI: PENDING / RUNNING / COMPLETED / FAILED
  end
  opt SME requests a financial assessment
    UI->>API: POST /companies/{id}/assessments
    API->>ANA: Assess immutable snapshot
    ANA->>DB: Save score, confidence references and versions
    API-->>UI: Assessment and explanatory factors
  end
  Note over ACC,DB: On process restart: unfinished jobs marked FAILED; user retries with a new job
```

## 06. Sequence — Consent, Lender Matching and Offer Selection

Privacy-safe discovery and transactional selection of an immutable loan offer.

```mermaid
sequenceDiagram
  autonumber
  actor SME
  actor Lender
  participant UI as Portals
  participant API as FastAPI
  participant ACCESS as access
  participant LEND as lending
  participant ANA as analysis
  participant DB as PostgreSQL

  SME->>UI: Create loan application
  UI->>API: POST /loan-applications
  API->>ACCESS: Verify SME ownership
  API->>LEND: Create DRAFT application
  LEND->>DB: Save draft

  SME->>UI: Publish + choose matching fields
  UI->>API: POST /loan-applications/{id}/publication
  API->>ACCESS: Check SME authority and disclosure scope
  API->>DB: Begin transaction
  API->>LEND: Publish application
  API->>ACCESS: Save matching disclosure / audit event
  API->>DB: Commit transaction
  API-->>UI: Application PUBLISHED

  Lender->>UI: Save lending criteria
  UI->>API: PUT /lenders/{id}/preferences
  API->>LEND: Validate officer permissions; save preferences
  Lender->>UI: Search for matching applications
  UI->>API: GET /lenders/{id}/matches
  API->>ACCESS: Determine published applications and permitted fields
  ACCESS-->>API: Authorized application IDs and field allowlists
  API->>LEND: Apply eligibility and rank only on authorized fields
  LEND->>ANA: Read permitted assessment summaries
  ANA-->>LEND: Authorized financial summaries
  LEND-->>API: Ranked, non-sensitive summaries
  API-->>UI: Matching applications only

  opt Lender needs additional financial details
    Lender->>UI: Request full review access
    UI-->>SME: Separate disclosure request
    SME->>UI: Approve or deny lender-specific access
    UI->>ACCESS: Save full review consent if approved
  end

  Lender->>UI: Submit binding-free demo offer
  UI->>API: POST /loan-applications/{id}/offers
  API->>ACCESS: Verify lender can offer on application
  API->>LEND: Store immutable SUBMITTED terms
  LEND->>DB: Insert offer and audit record atomically
  API-->>UI: New offer visible to SME

  SME->>UI: Select one offer
  UI->>API: POST /loan-offers/{id}/selection
  API->>ACCESS: Verify authorized SME user
  API->>DB: Begin transaction; lock application
  API->>LEND: Validate published state, offer status, single selection
  API->>LEND: Mark offer SELECTED; application OFFER_SELECTED
  API->>ACCESS: Record audit event
  API->>DB: Commit; enforce unique selected offer
  API-->>UI: Selected offer confirmed
```

## 07. Sequence — AI Advice and Deterministic What-if

Calculations remain deterministic, while the LLM only explains permitted aggregate results.

```mermaid
sequenceDiagram
  autonumber
  actor SME
  participant UI as SME Portal
  participant API as FastAPI
  participant ACCESS as access
  participant ANA as analysis / scenario engine
  participant ADV as advisory
  participant LLM as External LLM

  SME->>UI: Ask how reduced debt affects assessment
  UI->>API: POST /companies/{id}/scenarios
  API->>ACCESS: Verify company membership and permissions
  API->>ANA: Load immutable snapshot and validate scenario input
  ANA->>ANA: Apply consistent accounting assumptions
  ANA->>ANA: Recalculate metrics + illustrative assessment
  ANA-->>API: Before/after results; assumptions; quality flags
  API->>ADV: Explain verified scenario, not raw entries
  ADV->>LLM: Send minimum authorized aggregate metrics
  alt LLM available within timeout
    LLM-->>ADV: Natural-language explanation
  else Timeout, error, or disabled AI
    ADV->>ADV: TemplateAdapter deterministic explanation
  end
  ADV-->>API: Explanation + limitations
  API-->>UI: Scenario output + explanation
  Note over ANA,ADV: No modification to baseline snapshot or official assessment
```

## 08. Entity Relationships — Accounting and Analysis

Conceptual model of the versioned data pipeline; primary and foreign key names are illustrative.

```mermaid
erDiagram
  ORGANIZATION ||--o{ DATA_CONNECTION : owns
  DATA_CONNECTION ||--o{ IMPORT_JOB : starts
  DATA_CONNECTION ||--o{ IMPORT_BATCH : produces
  IMPORT_BATCH ||--o{ JOURNAL_ENTRY : contains
  IMPORT_BATCH ||--o{ FINANCIAL_SNAPSHOT : underlies
  FINANCIAL_SNAPSHOT ||--o{ FINANCIAL_METRIC : has
  FINANCIAL_SNAPSHOT ||--o{ CREDIT_ASSESSMENT : evaluated_by
  SCORECARD_VERSION ||--o{ CREDIT_ASSESSMENT : used_in
  MAPPING_VERSION ||--o{ FINANCIAL_SNAPSHOT : applied_to

  ORGANIZATION {
    uuid id PK
    string legal_name
    string type
  }
  DATA_CONNECTION {
    uuid id PK
    uuid organization_id FK
    string source_type
    string status
  }
  IMPORT_JOB {
    uuid id PK
    uuid connection_id FK
    string status
    datetime started_at
    string failure_reason
  }
  IMPORT_BATCH {
    uuid id PK
    uuid connection_id FK
    string content_hash
    datetime imported_at
  }
  JOURNAL_ENTRY {
    uuid id PK
    uuid batch_id FK
    string debit_account
    string credit_account
    decimal amount
  }
  FINANCIAL_SNAPSHOT {
    uuid id PK
    uuid organization_id FK
    uuid import_batch_id FK
    uuid mapping_version_id FK
    date period_end
  }
  FINANCIAL_METRIC {
    uuid id PK
    uuid snapshot_id FK
    string metric_code
    decimal value
    string formula_version
    string quality_flags
  }
  SCORECARD_VERSION {
    uuid id PK
    string version_label
  }
  MAPPING_VERSION {
    uuid id PK
    string version_label
  }
  CREDIT_ASSESSMENT {
    uuid id PK
    uuid snapshot_id FK
    uuid scorecard_version_id FK
    decimal illustrative_score
    string data_confidence
  }
```

## 09. Entity Relationships — Access and Lending

Conceptual model for organizations, publication permissions, applications, immutable offers and audit records.

```mermaid
erDiagram
  ORGANIZATION ||--o{ MEMBERSHIP : has
  USER ||--o{ MEMBERSHIP : participates
  ORGANIZATION ||--o{ LOAN_APPLICATION : submits
  ORGANIZATION ||--o{ LENDER_PREFERENCE : configures
  LOAN_APPLICATION ||--o{ DATA_DISCLOSURE : grants
  LOAN_APPLICATION ||--o{ LOAN_OFFER : receives
  ORGANIZATION ||--o{ LOAN_OFFER : proposes
  ORGANIZATION ||--o{ AUDIT_EVENT : triggers

  ORGANIZATION {
    uuid id PK
    string type
    string legal_name
  }
  USER {
    uuid id PK
    string email
  }
  MEMBERSHIP {
    uuid id PK
    uuid user_id FK
    uuid organization_id FK
    string role
  }
  LOAN_APPLICATION {
    uuid id PK
    uuid sme_org_id FK
    string status
    decimal requested_amount
    string currency
    int term_months
  }
  DATA_DISCLOSURE {
    uuid id PK
    uuid application_id FK
    string recipient_scope
    string level
    string purpose
    string permitted_fields
    datetime revoked_at
  }
  LENDER_PREFERENCE {
    uuid id PK
    uuid lender_org_id FK
    string criteria_version
  }
  LOAN_OFFER {
    uuid id PK
    uuid application_id FK
    uuid lender_org_id FK
    string status
    decimal interest_rate
    decimal fees
    int term_months
  }
  AUDIT_EVENT {
    uuid id PK
    uuid organization_id FK
    string action
    datetime occurred_at
  }
```

## 10. State Machine — Accounting Import Job

Manual retry creates a new job; unfinished jobs are failed on single-process startup.

```mermaid
stateDiagram-v2
  [*] --> PENDING: User starts import
  PENDING --> RUNNING: Background job starts
  RUNNING --> COMPLETED: Validated batch persisted
  RUNNING --> FAILED: API, validation or runtime failure
  PENDING --> FAILED: Restart before scheduling
  RUNNING --> FAILED: Single-process restart interrupts job
  COMPLETED --> [*]
  FAILED --> [*]
  note right of FAILED
    Manual Retry creates a NEW ImportJob.
    Previous valid financial snapshot remains available.
  end note
```

## 11. State Machine — Loan Application

Offers-received is a derived UI state, not a stored application status.

```mermaid
stateDiagram-v2
  [*] --> DRAFT: SME creates application
  DRAFT --> PUBLISHED: SME authorizes matching fields and publishes
  DRAFT --> WITHDRAWN: SME withdraws
  PUBLISHED --> WITHDRAWN: SME withdraws
  PUBLISHED --> OFFER_SELECTED: SME selects valid offer
  OFFER_SELECTED --> CLOSED: Workflow finished
  WITHDRAWN --> [*]
  CLOSED --> [*]
  note right of PUBLISHED
    Search only published applications.
    Enforce field-level matching consent.
    Offers received = derived from offer count.
  end note
```

## 12. State Machine — Loan Offer

Immutable offer terms; only an authorized SME can select; at most one SELECTED per application.

```mermaid
stateDiagram-v2
  [*] --> SUBMITTED: Lender submits immutable offer
  SUBMITTED --> SELECTED: SME selects under DB lock
  SUBMITTED --> REJECTED: SME rejects
  SUBMITTED --> WITHDRAWN: Lender withdraws
  SUBMITTED --> EXPIRED: Validity period ends
  SELECTED --> [*]
  REJECTED --> [*]
  WITHDRAWN --> [*]
  EXPIRED --> [*]
  note right of SUBMITTED
    Changes to terms require a new offer.
    One SELECTED offer per application (DB invariant).
  end note
```

## 13. Privacy Decision Flow — Matching Eligibility

Prevents indirect disclosure through filters, ranking, results, and counts.

```mermaid
flowchart TD
  START["Lender requests matches"] --> M["Authenticated officer belongs to lender organization?"]
  M -->|"No"| DENY["Deny request"]
  M -->|"Yes"| PUB["Published loan application?"]
  PUB -->|"No"| HIDE["Exclude from results / counts"]
  PUB -->|"Yes"| CONS["Valid matching disclosure for this lender?"]
  CONS -->|"No"| HIDE
  CONS -->|"Yes"| FIELDS["Requested filter and ranking fields allowlisted?"]
  FIELDS -->|"No"| REJECT["Reject unsupported criterion or omit field"]
  FIELDS -->|"Yes"| MATCH["Evaluate eligibility and rank using permitted metrics"]
  MATCH --> VIEW["Return allowed summary fields only"]
  VIEW --> FULL["Request for full financial review?"]
  FULL -->|"No"| END["End"]
  FULL -->|"Yes"| SPEC["Separate SME approval for specific lender"]
  SPEC -->|"Approved"| DETAIL["Grant purpose-scoped detailed view"]
  SPEC -->|"Denied"| END
  DETAIL --> END
```

## 14. Master Product Roadmap and Dependencies

Product milestones; validation can run in parallel with implementation.

```mermaid
flowchart TD
  M0["M0 Product specification"] --> M1["M1 Architecture baseline"]
  M1 --> M2["M2 Data integration"]
  M2 --> M3["M3 Financial intelligence"]
  M3 --> M4["M4 SME portal"]
  M4 --> M5["M5 Lender marketplace"]
  M3 --> M6["M6 AI and illustrative rate benchmark"]
  M5 --> M7["M7 End-to-end verification"]
  M6 --> M7
  M7 --> M8["M8 MVP demonstration"]
  M0 --> M9["M9 Market validation — parallel workstream"]
  M8 --> M10["M10 Pilot preparation"]
  M9 --> M10
  NOTE["Architecture document uses its own M0–M8 submilestones; this chart follows the Master Product Plan."]
  NOTE -.-> M1
```

## How to use

1. Open this `.md` file in VS Code Markdown Preview with Mermaid support, or view it in a GitHub repository that renders Mermaid code blocks.
2. To edit an individual diagram, use its `.mmd` source file, or paste the Mermaid block into [Mermaid Live Editor](https://mermaid.live/).
3. Keep the diagrams synchronized with ADRs, API contracts, and the implementation. Revise the sequences if bexio integration feasibility or permissions differ from current assumptions.
