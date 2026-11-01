# Vantage IQ

**See the business. Understand the signals. Act with confidence.**

Vantage IQ is an organization-scoped business intelligence SaaS foundation with a synthetic demo workspace. It includes a React dashboard, FastAPI API, cookie-based authentication, server-validated tenant membership and role checks, SQLAlchemy models, Alembic migrations, general business-record CRUD, revenue imports, and executive CSV/PDF reports.

> **Deployment status:** This is a production-oriented foundation, not a production-certified service. Email verification/recovery, persistent rate limiting, and tenant-scoped audit history are implemented. The portable Docker setup is provided but could not be built here because Docker is unavailable; live SMTP, production MySQL/TLS, operational controls, and independent review remain unverified. See [Known limitations](./docs/KNOWN_LIMITATIONS.md).

## Features

- Organization-scoped overview, financial, revenue, customer, project, department, budget, and alert APIs.
- Cookie-based login/logout with Argon2 password hashes, one-time email verification/recovery tokens, opaque hashed server-side sessions, CSRF validation, and organization selection.
- Database-backed rate limits, metadata-only tenant-scoped audit history, request IDs, and database/migration readiness checks.
- Role enforcement on the server: owners/admins can manage members and delete records, analysts can read/create/update, and viewers are read-only.
- Paginated create/read/update/delete APIs for customers, departments, projects, budgets, revenue transactions, and expenses.
- Responsive React/TypeScript workspace with role-aware record and team management.
- Alembic schema migration and repeatable synthetic seed data.
- Validated CSV/XLSX revenue import and organization-scoped executive CSV/PDF reports.
- KPI calculations document definitions and known exclusions; sales pipeline examples are labeled synthetic and are not recognized revenue.

## Local setup

### Portable container (Docker Compose)

Prerequisites: Docker Engine/Desktop with the Compose plugin and outbound access to download the pinned application dependencies during the first build. The image contains both the API and frontend; SQLite data is kept in a named persistent volume by default.

```sh
cp .env.example .env
docker compose up --build -d
```

Open [http://localhost:8080](http://localhost:8080). The API documentation and liveness/readiness checks are at `/docs`, `/api/v1/health`, and `/api/v1/ready` on that same origin. The default profile is a synthetic, read-only demo. `docker compose down` preserves the database volume.

To use it from another device on the same network, set `BIND_ADDRESS=0.0.0.0` and `TRUSTED_HOSTS` to include the machine's hostname/IP in `.env`, then rebuild/restart. Only expose the production deployment through a TLS reverse proxy.

For production with an externally managed MySQL server, SMTP relay, and TLS reverse proxy, create a private `.env` with the required production settings listed below, then run:

```sh
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build -d
```

Set `DATABASE_SSL_CA_HOST_PATH` to the CA file on the deployment machine. The production overlay mounts the CA read-only and the API verifies the database certificate/hostname. Startup migrations are enabled for the default single-instance deployment; run exactly one migration job before scaling and set `AUTO_MIGRATE=false` on application replicas.

### Run services without Docker

Prerequisites: Python 3.12+, Node.js 22+, and npm. The API defaults to local SQLite.

```sh
cp .env.example .env
# For this non-container workflow, set DATABASE_URL=sqlite:///./vantage_iq.db in .env.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head
PYTHONPATH=backend python -m app.seed_cli
PYTHONPATH=backend uvicorn app.main:app --reload
```

In another terminal:

```sh
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). To use MySQL, configure `DATABASE_URL` before applying migrations.

## Configuration and operation

See [.env.example](./.env.example). Important values:

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy database connection | local SQLite |
| `DEMO_MODE` | Enables the unauthenticated, read-only synthetic workspace | `true` |
| `ALLOW_REGISTRATION` | Enables public account/workspace registration outside demo mode | `false` |
| `SECRET_KEY` | HMAC key for session/CSRF token digests; use a random secret of at least 32 bytes in production | unset |
| `SESSION_COOKIE_SECURE` | Requires HTTPS for the session and CSRF cookies | inferred from `APP_ENV` |
| `CORS_ORIGINS` | Explicit browser origin allowlist | local Vite/Compose origins |
| `PUBLIC_APP_URL` | Origin used to build verification and recovery links | `http://localhost:5173` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_ADDRESS` | SMTP delivery for account emails | unset |
| `SMTP_STARTTLS` | Require STARTTLS for SMTP | `true` |
| `TRUSTED_HOSTS` | Explicit HTTP host allowlist | local hosts |
| `DATABASE_SSL_CA` | Absolute CA path for verified MySQL TLS | unset |
| `AUTH_ACTION_TOKEN_TTL_MINUTES` | Verification/reset token expiry | 60 |
| `UPLOAD_MAX_BYTES` | Maximum import file size | 5 MiB |
| `VITE_API_URL` | API URL embedded in the frontend build; leave empty for same-origin container hosting | empty |

The container applies Alembic migrations at startup for a single-instance deployment; it does not call `create_all()`. Run one migration job before scaling and disable `AUTO_MIGRATE` on replicas. Demo seeding runs at startup only when `DEMO_MODE=true`.

Set `APP_ENV=production`, `DEMO_MODE=false`, a sufficiently long `SECRET_KEY`, `SESSION_COOKIE_SECURE=true`, an HTTPS-only `CORS_ORIGINS` and `PUBLIC_APP_URL`, MySQL `DATABASE_URL` plus `DATABASE_SSL_CA`, SMTP with STARTTLS, and explicit `TRUSTED_HOSTS` for production configuration validation. Configure registration deliberately; it is disabled by default. See the [deployment guide](./docs/DEPLOYMENT_GUIDE.md).

## Data calculations

- Revenue means recognized revenue transactions only. Pipeline examples are separate and demo-only.
- Operating profit is recognized revenue minus recorded operating expenses; it is not net profit or EBITDA.
- Operating margin is unavailable when recognized revenue is zero or negative.
- Revenue refunds and expense credits may be negative. No FX conversion is applied.
- Revenue target achievement prorates monthly targets over the selected date period.
- On-time delivery counts completed projects with an actual end date; incomplete work is excluded.
- Customer activity is not a cohort retention, churn, ARR/MRR, or lifetime-value measure.
- Company-wide expenses are not allocated to departments.

## Tests and build

```sh
PYTHONPATH=backend python -m pytest -q backend/tests
cd frontend
npm run build
npm audit
```

The backend tests cover calculations, deployment settings, account verification/recovery, session/CSRF, audit history, readiness, organization switching, tenant isolation, role checks, and PDF response generation. Browser automation, live SMTP, MySQL/TLS integration, and production deployment validation remain outstanding.

## Documentation

- [API reference](./docs/API_REFERENCE.md)
- [Database schema](./docs/DATABASE_SCHEMA.md)
- [System architecture](./docs/SYSTEM_ARCHITECTURE.md)
- [Security notes](./docs/SECURITY.md)
- [Deployment guide](./docs/DEPLOYMENT_GUIDE.md)
- [Testing guide](./docs/TESTING.md)
- [Known limitations](./docs/KNOWN_LIMITATIONS.md)
- [Product requirements and scope](./docs/PRODUCT_REQUIREMENTS.md)
- [KPI dictionary](./docs/KPI_DICTIONARY.md)
- [Data import guide](./docs/DATA_IMPORT_GUIDE.md)
- [User guide](./docs/USER_GUIDE.md)
