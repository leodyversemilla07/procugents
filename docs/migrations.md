# Database migrations

ProCuGents uses [Alembic](https://alembic.sqlalchemy.org/) for production
schema management (PostgreSQL) and falls back to `Base.metadata.create_all`
on SQLite for local development convenience.

## First-time setup (PostgreSQL)

```bash
# 1. Export the same env vars your runtime uses
export POSTGRES_HOST=db
export POSTGRES_PORT=5432
export POSTGRES_USER=procuregents
export POSTGRES_PASSWORD=...
export POSTGRES_DB=redflag_agents

# 2. Apply the baseline
alembic upgrade head

# 3. Start the API
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

The baseline migration `2026_07_08_00` creates all three tables and
seeds the `alembic_version` row. After this, the database is under
migration control and `init_db()` refuses to silently bypass alembic.

## Authoring new migrations

Alembic does not autogenerate reliably for our JSONB columns on
PostgreSQL, so author by hand:

```bash
# 1. Generate a templated, empty migration:
alembic revision -m "add created_by column to procurement_analysis"

# 2. Edit alembic/versions/<rev>_*.py:
#    * upgrade(): op.add_column(...)
#    * downgrade(): op.drop_column(...)

# 3. Test locally against SQLite:
alembic upgrade head
alembic downgrade -1

# 4. Test against your local PostgreSQL:
POSTGRES_PASSWORD=... alembic upgrade head

# 5. Commit the migration file alongside the model change.
```

## Production hardening (built into `init_db`)

`src.services/database.py`'s `init_db()` deliberately refuses to be the
fast path on PostgreSQL. It inspects the database and raises a clear
`RuntimeError` if:

* The `alembic_version` table is missing (no migrations run), or
* Any of the application tables (`procurement_analysis`, `alerts`,
  `agencies`) is missing despite the version table being present.

This forces every operator to run `alembic upgrade head` rather than
silently creating tables that alembic doesn't know about, which would
break later.

On SQLite (the dev default), `init_db()` still calls
`Base.metadata.create_all` for fast iteration; this is the only environment
where the dev-fallback is acceptable.

## Tests

`tests/test_migrations.py` covers:

* SQLite `init_db()` happy path produces all three application tables but
  leaves the schema unmanaged (alembic_version absent).
* `init_db()` raises on PostgreSQL when the schema lacks `alembic_version`.
* `init_db()` raises when application tables are missing.
* `alembic upgrade head` creates the right tables from a clean DB.
* `alembic upgrade head` → `downgrade base` → `upgrade head` round-trip
  preserves schema invariants.

## Architectural notes

* `src/services/db_models.py` contains only the declarative `Base` and
  table definitions — no engine, no session. This module is safe for
  alembic's `env.py` to import without triggering runtime side-effects.
* `src/services/database.py` holds the engine, session factory, and the
  production-hardened `init_db()`. It re-exports the public names
  (`AnalysisStatus`, `ProcurementAnalysis`, etc.) for backwards
  compatibility with callers that imported them from this module before
  the split.
