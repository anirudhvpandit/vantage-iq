# Vantage IQ — product overview

**See the business. Understand the signals. Act with confidence.**

Vantage IQ is an organization-scoped business intelligence SaaS foundation for financial performance, revenue, project delivery, and customer contribution. The synthetic demo provides a coherent fixed sample; authenticated organizations use the same tenant-scoped API and KPI calculations with their own records.

## Demonstrated capabilities

- Database-backed, filter-aware executive overview and financial/project/customer views.
- Cookie-based authentication, organization membership/switching, CSRF controls, and server-enforced roles and tenant access.
- Create/read/update/delete APIs and frontend management for core business records.
- Alembic-managed schema and repeatable synthetic seed data.
- Validated CSV/XLSX revenue import for authorized organizations.
- Tenant-scoped executive CSV and PDF reports.
- KPI definitions, formulas, and explicit data limitations.

## Important boundary

This is not a production-certified service. Email verification, account recovery, persistent database-backed rate limiting, and tenant-scoped audit history are implemented. Live SMTP delivery, production MySQL/TLS validation, monitoring, backup/restore procedures, and independent review remain outstanding. Review [Security](./SECURITY.md) and [Known limitations](./KNOWN_LIMITATIONS.md) before deployment; do not treat the synthetic data as live customer evidence.
