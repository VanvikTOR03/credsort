<div align="center">

# CredSort

**One profile. Many lenders. Your best rate.**

A Swiss marketplace where small and medium-sized companies (SMEs) get comparable loan offers from banks and other lenders, based on their real accounting data.

FinTech Certificate Programme · University of St. Gallen (HSG)

</div>

---

## Why CredSort

Swiss SMEs usually ask one or two banks for credit, with little idea what a fair rate is. Lenders, in turn, spend time on applications that never fit their book.

CredSort turns a company's accounting data into one standardised financing profile. The company decides exactly what lenders may see, matching lenders send offers, and the company picks the one with the lowest total cost.

| For companies | For lenders |
|---|---|
| Connect accounting (bexio) once, get a transparent credit-health score | Only see companies that match your own criteria |
| Try what-ifs: how would lower costs or less debt change the score? | Standardised, verified figures instead of PDF piles |
| Share only the details you choose and revoke access at any time | Ask for more detail with one click; the company decides |
| Compare offers by **total cost**, including all fees | Simple offer flow, payout confirmation, clear pipeline |
| **Free to use: a success fee applies only if a loan is paid out** | |

## How it works

```mermaid
flowchart LR
  A[Connect accounting] --> B[Score and profile]
  B --> C[Choose what lenders see]
  C --> D[Matching lenders send offers]
  D --> E[Compare total cost and choose]
  E --> F[Lender confirms payout]
  F --> G[14-day window to report a problem]
```

- CredSort **never handles loan money**. Lenders pay out directly.
- The fee is fixed with a signed quote when an offer is made, locked when the company chooses it, and payable only after the 14-day window.
- Matching uses only the fields the company shared. Fees never influence ranking.

## Architecture

Service-based architecture with event-driven integration, chosen for confidentiality, data integrity and evolvability. Details in [docs/architecture](docs/architecture/README.md) and [31 architecture decision records](docs/adr/README.md).

```mermaid
flowchart TB
  Browser --> Web["Web app + BFF (Next.js)"]
  Web --> Identity & Accounting & Intelligence & Marketplace & Billing & Advisory & Notification & Audit
  Accounting -- events --> Broker[(Message broker)]
  Intelligence & Marketplace & Billing & Notification & Audit <-- events --> Broker
  Accounting --> bexio[(bexio API)]
```

| Service | Responsibility |
|---|---|
| **identity** | Organisations, members, verification, accountant delegation, short-lived context tokens |
| **accounting** | Accounting connections (bexio, demo data) and background imports |
| **intelligence** | Financial data pipeline: mapping, metrics, scorecard, what-if scenarios |
| **marketplace** | Loan requests, consent, frozen published profiles, matching, offers, payout and disputes |
| **billing** | Price books, signed fee quotes, charges (exactly as quoted) |
| **advisory** | Plain-language explanations; AI only explains, never invents numbers |
| **notification** | In-app notifications without financial values |
| **audit** | Tamper-evident (hash-chained) activity log |

Key properties: one database per service, row-level security for every tenant table, transactional outbox and idempotent inbox, money as exact decimals, contracts generated and checked in CI ([contracts/](contracts)).

**Tech stack:** Python · FastAPI · PostgreSQL · RabbitMQ · Keycloak · Next.js · TypeScript

## Getting started

Requirements: Python 3.11+, Node.js 20+. No Docker needed for local development.

**1. Install**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e "libs/credsort-common[test]" pgserver
cd web && npm install && cd ..
```

**2. Start the backend** (embedded PostgreSQL, all services, demo data)

```bash
python scripts/dev_up.py
```

Wait for `seed done`.

**3. Start the web app** (second terminal)

```bash
cd web && npm run dev
```

Open **http://localhost:3000** and pick a demo profile. All data is synthetic and the dev login needs no password.

### Demo walkthrough

| Step | Sign in as | Do |
|---|---|---|
| 1 | Anna Keller (company) | Check the score, try a what-if, publish a loan request |
| 2 | Sandra Huber (lender) | Open the match, send an offer |
| 3 | Anna Keller | Compare offers and choose one |
| 4 | Sandra Huber | Confirm the payout |
| 5 | Anna Keller | See the 14-day window and the fee |
| 6 | CredSort Operations | Review charges and pricing |

Also try Marco Rossi (accountant) to work on behalf of a client company.

**Reset demo data:** stop the backend, delete `.dev/pg`, start it again.

## Tests

```bash
# unit tests per service
for d in libs/credsort-common services/*; do (cd $d && PYTHONPATH=$PWD python -m pytest -q); done

# architecture fitness functions, contract drift and end-to-end (backend must be running)
python -m pytest tests -q
```

Regenerate API and event contracts after interface changes: `python scripts/gen_contracts.py`.

## Project structure

```
services/        8 backend services (FastAPI), each with its own migrations and tests
libs/            shared technical library (outbox/inbox, tokens, RLS sessions, resilient HTTP)
web/             Next.js web app and BFF
contracts/       generated OpenAPI and event schemas
tests/           architecture fitness functions and end-to-end tests
scripts/         local stack, demo seed, contract generation
deploy/          Docker Compose, Keycloak and RabbitMQ configuration
docs/            architecture views and ADRs
```

## Status

MVP under development.

- **Working and tested locally:** all services, the end-to-end loan flow, the web app for companies, lenders, accountants and operators.
- **Not yet tested:** the Docker Compose deployment, RabbitMQ, Keycloak sign-in (a dev login stands in), the live bexio connection, the optional AI language model.
- **Open decisions:** the SME fee amount (a labelled demo price book is used), the lender fee, legal review (nFADP, AML, credit intermediation).

## Documentation

- [Architecture overview](docs/architecture/README.md)
- [Architecture decision records](docs/adr/README.md)
- [Product and development plan](docs/CredSort_Master_Product_Development_Plan_EN_v1.md)
- [Architecture and implementation plan](docs/CredSort_Architecture_Implementation_Plan_EN_v1.md)
