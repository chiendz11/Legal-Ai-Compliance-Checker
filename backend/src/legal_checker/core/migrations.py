"""Versioned PostgreSQL migrations, independent of development/Excel tooling."""

import hashlib
from importlib.resources import files


def migrate(connection) -> None:
    connection.execute("SELECT pg_advisory_xact_lock(743249)")
    connection.execute("CREATE SCHEMA IF NOT EXISTS dev_meta")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS dev_meta.schema_migrations (
            version INTEGER PRIMARY KEY, sha256 TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    root = files("legal_checker.core").joinpath("sql")
    for resource in sorted(root.iterdir(), key=lambda item: item.name):
        if not resource.name.endswith(".sql"):
            continue
        version = int(resource.name.split("_", 1)[0])
        migration = resource.read_text(encoding="utf-8")
        checksum = hashlib.sha256(migration.encode()).hexdigest()
        applied = connection.execute(
            "SELECT sha256 FROM dev_meta.schema_migrations WHERE version=%s", (version,)
        ).fetchone()
        if applied:
            if applied["sha256"] != checksum:
                raise ValueError(f"Migration {version} checksum changed; create a new migration")
            continue
        connection.execute(migration)
        if version == 1:
            connection.execute("""
                CREATE TABLE dev_meta.seed_imports (
                    source_sha256 TEXT PRIMARY KEY, row_counts JSONB NOT NULL,
                    imported_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
        connection.execute(
            "INSERT INTO dev_meta.schema_migrations VALUES (%s, %s, now())", (version, checksum)
        )
