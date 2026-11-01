# Testing

## Backend

```sh
PYTHONPATH=backend python -m pytest -q backend/tests
```

The SQLite-backed API tests cover registration/session cookies, CSRF persistence across `/auth/me`, logout revocation, organization switching, tenant isolation, viewer write denial, PDF response generation, and production configuration validation. Calculation tests cover decimal percentage change, zero baselines, negative revenue boundaries, and budget achievement.

## Migration smoke test

Use a disposable SQLite database path:

```sh
PYTHONPATH=backend DATABASE_URL=sqlite:////tmp/vantage-iq-migration.db \
  alembic -c backend/alembic.ini upgrade head
PYTHONPATH=backend DATABASE_URL=sqlite:////tmp/vantage-iq-migration.db \
  alembic -c backend/alembic.ini current
```

## Frontend

```sh
cd frontend
npm run build
npm audit
```

## Remaining verification

MySQL integration, browser flows, accessibility audits, import edge cases against a production database, concurrent login/session behavior, distributed rate limits, load/performance baselines, backup/restore, and security review are not covered by the current automated tests.
