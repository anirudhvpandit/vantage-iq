# API reference

Interactive OpenAPI is available at `/docs` when the API is running. Base path: `/api/v1`. Responses are JSON unless noted. Authenticated requests use the `vantage_session` cookie. Unsafe requests require `X-CSRF-Token`; the frontend obtains it from the `vantage_csrf` cookie. `X-Organization-ID` is an organization-selection hint, not an authorization credential.

## Authentication and organizations

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness status and mode |
| `GET` | `/ready` | Database connectivity and current Alembic-head readiness |
| `GET` | `/config` | Public registration setting, import limits, and role definitions |
| `POST` | `/auth/register` | Create an unverified account and organization; attempts verification email and returns 202; requires `ALLOW_REGISTRATION=true` |
| `POST` | `/auth/verify-email` | Consume a one-time email verification token |
| `POST` | `/auth/verification/resend` | Resend verification instructions without revealing account existence |
| `POST` | `/auth/password-reset/request` | Request password reset instructions without revealing account existence |
| `POST` | `/auth/password-reset/complete` | Consume a one-time password reset token and revoke existing sessions |
| `POST` | `/auth/login` | Authenticate and create a server-side session |
| `GET` | `/auth/me` | Current user and organization memberships |
| `POST` | `/auth/logout` | Revoke current session |
| `GET` | `/organizations` | Organizations for the current user |
| `POST` | `/organizations/{organization_id}/switch` | Change active organization after membership and CSRF validation |
| `GET` | `/organizations/{organization_id}/members` | List members; owner/admin only |
| `POST` | `/organizations/{organization_id}/members` | Add an existing account; owner/admin only |
| `PATCH` | `/organizations/{organization_id}/members/{user_id}` | Update membership role; owner/admin only |
| `DELETE` | `/organizations/{organization_id}/members/{user_id}` | Remove member; owner/admin only |
| `POST` | `/organizations` | Create an organization and owner membership |
| `GET` | `/audit-events` | Paginated organization audit history; owner/admin only |

Roles: owner/admin have read, write, delete, and member-management access; analyst has read/create/update access; viewer has read-only access. The API validates the selected organization against the authenticated user’s memberships on every request.
Account action tokens are random, single-use, time-limited, and stored as HMAC digests. Account lifecycle emails use configured SMTP with STARTTLS; recovery/resend responses do not confirm account existence or delivery, and delivery failures are logged. Authentication and registration endpoints use persistent database-backed fixed-window rate limits and return HTTP 429 with `Retry-After` when exceeded. Responses include a server-generated `X-Request-ID`.

## Analytics and reports

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/overview?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | Period KPIs and trends |
| `GET` | `/financial` | Financial metrics and formula limitations |
| `GET` | `/revenue/analytics` | Recognized revenue by customer and demo-only synthetic pipeline examples |
| `GET` | `/projects/health` | Project health and on-time definition |
| `GET` | `/customers/analytics?search=text` | Customer contribution, account owner, status, and last transaction date |
| `GET` | `/alerts` | Organization-scoped alerts |
| `GET` | `/reports/executive.csv` | Filter-aware executive CSV |
| `GET` | `/reports/executive.pdf` | Executive PDF |

## Business-record CRUD

Customer, department, project, budget, revenue, and expense resources support `GET` collection, `POST`, `GET /{id}`, `PATCH /{id}`, and `DELETE /{id}` routes (departments/budgets/revenue/expenses and the tenant-scoped customer/project lists are paginated with `limit` and `offset`). Create/update payloads reject unknown fields and cannot set `organization_id`; related customer/department IDs must belong to the active organization.

## Imports

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/imports/revenue/template.csv` | Revenue CSV template |
| `GET` | `/imports/revenue/template.xlsx` | Revenue XLSX template |
| `POST` | `/imports/revenue/preview` | Multipart `file`; returns valid-row count, sample, and row errors |
| `POST` | `/imports/revenue/commit` | Multipart `file` plus `confirm=true`; inserts only an entirely valid file |

Required headers: `external_id,date,customer,department,amount,currency,description`. Existing customer and department names must match within the selected organization. Amounts may be negative for refunds. Currency must match the organization currency; no FX conversion is applied. Uploads are limited by `UPLOAD_MAX_BYTES`, 10,000 rows, 50 columns, and `.csv`/`.xlsx` formats.

## Errors

FastAPI validation errors use HTTP 422. Unsupported formats return 415, oversized files return 413, duplicate/conflicting records return 409, unauthenticated requests return 401, insufficient permissions/CSRF return 403, rate-limit violations return 429, and resources outside the selected tenant return 404.
