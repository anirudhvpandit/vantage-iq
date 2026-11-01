# Portfolio case study: Vantage IQ

## Business problem

Small project-driven businesses often reconcile multiple spreadsheets to understand whether revenue, costs, project delivery, and customer contribution are moving together. Vantage IQ explores a consolidated executive view while making source limitations visible.

## Users and requirements

The target audience is founders, finance leaders, operations managers, department leads, and project managers. The MVP focuses on an interactive summary, date comparisons, drill-downs, metric definitions, safe revenue-file validation, and a downloadable report.

## Architecture and data model

The frontend is React/TypeScript with Vite, TanStack Query, and Chart.js. A FastAPI/SQLAlchemy modular monolith provides JSON and file endpoints. SQLite supports quick local use; Compose configures MySQL 8. The schema models organizations, departments, customers, financial transactions, budgets, projects, and alerts. Financial amounts use decimal database types.

## KPI methodology

Recognized revenue is kept separate from synthetic pipeline examples. Operating profit equals recognized revenue less recorded operating expenses and is not described as EBITDA or net profit. Margin is unavailable for zero/negative revenue. Period comparisons handle a zero baseline explicitly. On-time delivery only includes completed projects with actual completion dates. Customer activity is disclosed as an activity proxy, not cohort retention.

## Security and integrity

The API uses Argon2 password hashes, opaque server-side sessions, CSRF token validation, explicit CORS origins, and membership-derived organization context. Tenant queries and related-record IDs are organization-scoped; role checks run on the server. Imports validate extension, size, columns, amount/date values, and duplicate IDs before a separately confirmed transactional commit. XLSX values are read without macro execution. CSV export escapes formula-like text. These controls are a foundation, not a security certification.

## Synthetic results

Northstar Industrial Services is entirely fictional. Its 24-month dataset includes twelve synthetic customers, four departments, revenue, expenses, monthly budgets, and project examples with mixed status and delivery outcomes. Displayed values are seeded illustrative outputs, not customer evidence or validated business results.

## Trade-offs and next steps

The modular monolith keeps the service inexpensive to run and reason about. A fixed synthetic snapshot avoids implying live data freshness. The system includes tenant-safe identity and authorization foundations, Alembic migrations, core CRUD, CSV/PDF reports, account verification/recovery, persistent rate limits, audit history, and a portable single-container deployment path. Remaining work includes validating the container build, live email delivery, production MySQL/TLS, and operational hardening before commercialization.
