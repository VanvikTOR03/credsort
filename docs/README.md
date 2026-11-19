# CredSort

**One Profile. Many Lenders. Your Best Rate.**

CredSort is a Swiss FinTech platform connecting small and medium-sized enterprises (SMEs) with banks and other lenders.

By integrating with accounting software such as bexio, CredSort analyzes financial data, generates standardized creditworthiness assessments, and helps SMEs find competitive financing offers.

### Key Features

- **Accounting Integration:** Automated financial data import via bexio API.
- **Financial Assessment:** Credit scoring based on financial indicators.
- **Lender Matching:** Customizable filters to connect lenders with suitable SMEs.
- **Loan Comparison:** Compare interest rates and financing conditions.
- **AI Financial Advisor:** Personalized financial insights and recommendations.
- **Data Security:** Controlled access to confidential financial information.

### Technology

Service-based architecture: Next.js (web app + BFF) · FastAPI services (Python) · PostgreSQL (one database per service) · RabbitMQ · Keycloak · bexio API

### Documentation

- [Architecture overview](architecture/README.md): review, use case and screens, domain and service model, architecture characteristics, style selection and trade-offs, runtime and integration, failure modes, security, deployment
- [Architecture Decision Records](adr/README.md): 31 ADRs
- [Master Product & Development Plan v1](CredSort_Master_Product_Development_Plan_EN_v1.md)
- [Architecture & Implementation Plan v1](CredSort_Architecture_Implementation_Plan_EN_v1.md)
- [Diagrams as Code](CredSort_Diagrams_as_Code_EN.md)

### Project Status

Under development as part of the **FinTech Certificate Programme at the University of St. Gallen (HSG)**.

The project is currently focused on building a functional MVP.
