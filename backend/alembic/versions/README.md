# Database migrations

Reserved for future Alembic migrations; Alembic is not configured yet.

Local PostgreSQL currently uses the versioned SQL migration at
`src/legal_checker/core/sql/001_workbook_v7_4_9.sql`, tracked in `dev_meta.schema_migrations`.
Run `python -m scripts.local_db init` from the repository root. See
[local database setup](../../../docs/local_database.md).

The existing API SQLite repository still initializes its MVP tables directly.
