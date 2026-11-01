# Design decisions and trade-offs

- **Modular monolith:** one FastAPI service and one React app keep a first MVP operable without distributed infrastructure.
- **SQLAlchemy + SQLite/MySQL:** SQLite simplifies local exploration; Compose demonstrates MySQL compatibility. Alembic migrations are the schema deployment mechanism; API startup does not create tables.
- **Synthetic fixed snapshot:** repeatable 24-month data gives stable reports and avoids implying live connections.
- **Metric restraint:** operating profit is not labeled EBITDA/net profit; customer activity is not labeled cohort retention; forecasts are omitted rather than overstated.
- **Date filters are API inputs:** selected periods affect server aggregations, comparisons, budget prorating, and chart query state.
- **CSV/XLSX only for imports:** spreadsheet macros are not executed; exact-name lookup and stable external IDs avoid hidden upserts.
- **Separate preview and commit:** commit requires explicit confirmation and revalidation, with transaction rollback on failure.
- **CSV and PDF reports:** both are generated server-side from tenant-scoped calculations; spreadsheet exports guard against formula-like text.
- **No identity pretence:** the demo displays no fabricated signed-in user and labels the single synthetic workspace; authenticated users are derived from server-side sessions.
- **Custom CSS design tokens:** a small CSS system avoids a large styling dependency; React Router and form libraries support the authenticated workspace.
