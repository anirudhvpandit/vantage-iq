# Security notes

## Implemented controls

- Argon2 password hashing and opaque, random session tokens; only HMAC digests of session and CSRF tokens are stored.
- HttpOnly, SameSite=Lax session cookies; production configuration requires Secure cookies and HTTPS CORS origins.
- A host-only readable CSRF cookie is checked against the session’s stored CSRF digest. Unsafe tenant API requests require the matching `X-CSRF-Token`.
- Organization membership is derived from the authenticated server-side session. Every tenant data query/mutation scopes records to the active organization; caller-supplied tenant IDs are rejected from record payloads.
- Server-side role checks distinguish read, create/update, delete, and member-management permissions. Related records are validated to belong to the same organization.
- CORS origins are explicit; wildcard origins are rejected.
- Password and registration request schemas reject extra fields; passwords have length bounds; account registration is disabled by default.
- Email verification and password recovery use random, time-limited, one-time tokens; only HMAC digests are stored. Resetting a password revokes existing sessions.
- Account lifecycle email is sent over SMTP with STARTTLS. Production configuration requires SMTP, HTTPS app/CORS origins, verified MySQL TLS CA configuration, explicit trusted hosts, and secure cookies.
- Login, registration, verification, and password reset use persistent database-backed fixed-window rate limits. Rate-limit identities are HMACed; responses include `Retry-After`.
- ORM flush listeners persist metadata-only audit events in the same transaction as audited business/account mutations. Organization owners/admins can read paginated, tenant-scoped history. A generated `X-Request-ID` is included in API responses and audit rows.
- `/ready` checks database connectivity and that the schema is at the current Alembic head; `/health` is a liveness endpoint.
- Revenue file imports enforce file/row/column limits and all-or-nothing transaction semantics. CSV exports protect against spreadsheet formula injection.
- Alembic revisions are the schema deployment mechanism; API startup does not create tables.

## Required before handling production data

- Configure and verify the actual production SMTP relay and domain deliverability. Mail delivery failures are logged while public account-action responses remain generic to avoid account enumeration; monitor those logs operationally.
- Validate the migrations and application against the intended production MySQL version, CA chain, TLS hostname verification, and concurrent deployment topology. These integrations have not been verified in this workspace.
- Configure TLS termination and trusted proxy handling. The API redirects HTTP in production; only trust forwarding headers from the intended proxy.
- Protect audit history against privileged database tampering and define retention/access policies. Application audit events are metadata-only, append-oriented records, not a tamper-proof external ledger.
- Independently review authentication, tenant isolation, role transitions, import paths, and PDF/CSV exposure. The included tests are not a security certification.
- Configure secret storage/rotation, database backups and restore drills, monitoring/alerting, vulnerability scanning, and data-retention/privacy controls.
- Restrict public registration to an approved onboarding policy. It remains disabled by default.

The demo workspace is synthetic and unauthenticated, and is read-only for business records. Do not expose demo mode as a production tenant.
