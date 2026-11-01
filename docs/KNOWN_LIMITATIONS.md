# Known limitations

- This is a production-oriented SaaS foundation, not a production-certified service.
- Public registration is configurable and disabled by default. Verification and password recovery require a correctly configured, deliverable SMTP service; live SMTP has not been verified.
- Persistent fixed-window rate limits are database-backed, but account lockout, configurable per-route policies, and production abuse monitoring are not provided.
- Audit-event persistence and owner/admin tenant-scoped history are implemented. The log is not tamper-proof against privileged database access; retention and external archival policies are not configured.
- Production settings require verified MySQL TLS, SMTP STARTTLS, HTTPS origins, and explicit trusted hosts, but validation has only been exercised locally; production MySQL and TLS deployment are unverified.
- `/ready` validates database connectivity and Alembic head; Docker/MySQL deployment was not verified in this environment.
- No browser-level end-to-end, concurrency, performance, external security review, backup/restore, or disaster-recovery tests have been run.
- Team management can add existing accounts; invitations and onboarding emails are not implemented.
- Demo opportunities are static examples and not persisted sales opportunities.
- No foreign-exchange conversion, accounting-period calendars, timezone configuration, expense allocation, ARR/MRR, EBITDA, net profit, churn, customer lifetime value, or cohort retention are modeled.
- Demo data is a fixed November 2024–October 2026 synthetic snapshot and is not refreshed from live data.
- No in-product demo reset control, import history/rollback, or versioned reports are provided.
