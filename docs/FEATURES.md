# Implemented versus deferred

## Implemented

- React/TypeScript SPA with responsive shell, routed navigation, date filters, light/dark mode, error/loading states, and page search.
- FastAPI analytics for overview, financial performance, revenue, customers, projects, and alerts.
- Cookie-based user sessions, configurable registration, organization membership/switching, CSRF validation, and server-side role/tenant authorization.
- Email verification and password recovery with one-time tokens, SMTP STARTTLS, and enumeration-resistant responses.
- Persistent fixed-window authentication rate limits, request IDs, and owner/admin tenant-scoped audit history.
- Database and Alembic-head readiness endpoint with production MySQL TLS configuration gates.
- Organization-scoped list/create/read/update/delete API routes and frontend record management for customers, departments, projects, budgets, revenue, and expenses.
- Paginated list APIs, team membership and role management for existing accounts, and viewer/read-write permissions.
- Alembic initial schema migration and repeatable deterministic demo seed.
- Revenue CSV/XLSX templates, preview validation, dedupe, and confirmed transactional commit for authenticated organizations.
- Executive CSV and PDF report endpoints.
- Calculation, auth/API, tenant-isolation, role, deployment-config, and PDF response tests.
- Product, architecture, schema, API, KPI, user, import, deployment, testing, security, roadmap, product overview, case study, example report, and limitation documentation.

## Deferred

- Team invitations/onboarding emails and audited data-retention controls.
- Persistent opportunity lifecycle, milestones, KPI target editing, and full alert management UI.
- Billing entitlements, advanced forecasting, foreign-exchange conversion, and accounting-period/time-zone configuration.
- Live SMTP delivery, production MySQL/TLS integration, deployment observability, load testing, backup restore verification, and comprehensive browser/security test suites.
