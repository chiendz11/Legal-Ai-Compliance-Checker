"""Alembic entrypoints shared by CLI/tests; repositories still use psycopg directly."""

import hashlib
import json
from importlib.resources import files
from threading import RLock

import psycopg
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from legal_checker.migrations.schema_state import structure_fingerprints

_ALEMBIC_COMMAND_LOCK = RLock()


class MigrationAdoptionError(ValueError):
    """Legacy schema/history differs; no automatic stamp or repair was performed."""


def sql_resource_checksum(content: bytes) -> str:
    """Verify frozen LF SQL across checkout/package CRLF conversion only.

    Git may materialize the same tracked SQL with CRLF on Windows. The frozen
    baseline describes LF bytes; no other whitespace, Unicode or SQL contents
    are normalized, and persisted migration checksums must still match exactly.
    """
    return hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()


def alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", "legal_checker:migrations")
    return config


def migration_engine(database_url: str):
    # Creator accepts both PostgreSQL URLs and libpq DSNs, without quoting secrets into config.
    return create_engine(
        "postgresql+psycopg://",
        creator=lambda: psycopg.connect(database_url, connect_timeout=10),
        poolclass=NullPool,
    )


def upgrade_database(database_url: str) -> None:
    engine = migration_engine(database_url)
    try:
        # Alembic's context proxy is process-global. The database advisory lock in
        # env.py serializes separate processes; this lock also protects threads.
        with _ALEMBIC_COMMAND_LOCK, engine.begin() as connection:
            config = alembic_config()
            config.attributes.update(connection=connection, allow_legacy_adoption=True)
            command.upgrade(config, "head")
    finally:
        engine.dispose()


def checked_legacy_revision(connection) -> str | None:
    """Called under the migration lock, before Alembic creates its version table."""
    present = (
        connection.execute(
            text("""
        SELECT to_regclass('dev_meta.alembic_version') IS NOT NULL AS alembic,
               to_regclass('dev_meta.schema_migrations') IS NOT NULL AS legacy
    """)
        )
        .mappings()
        .one()
    )
    if present["alembic"]:
        return None
    actual = structure_fingerprints(connection)
    if not present["legacy"]:
        if actual:
            raise MigrationAdoptionError(
                "Existing unversioned schema; reconcile it before migration"
            )
        return None
    history = (
        connection.execute(
            text("SELECT version, sha256 FROM dev_meta.schema_migrations ORDER BY version")
        )
        .mappings()
        .all()
    )
    if not history and not actual:
        return None
    root = files("legal_checker.migrations")
    baselines = json.loads(root.joinpath("legacy_baselines.json").read_text(encoding="utf-8"))
    versions = [row["version"] for row in history]
    if not versions or versions != list(range(1, versions[-1] + 1)):
        raise MigrationAdoptionError("Legacy migration history is incomplete")
    baseline = baselines.get(str(versions[-1]))
    if baseline is None:
        raise MigrationAdoptionError("Unsupported legacy migration version")
    for row in history:
        expected = baselines[str(row["version"])]["sql_sha256"]
        resource = root.joinpath("sql", baselines[str(row["version"])]["sql_file"])
        if row["sha256"] != expected or sql_resource_checksum(resource.read_bytes()) != expected:
            raise MigrationAdoptionError("Legacy migration checksum differs; adoption refused")
    expected = baseline["objects"]
    changed = sorted(
        key for key in set(actual) | set(expected) if actual.get(key) != expected.get(key)
    )
    if changed:
        raise MigrationAdoptionError("Legacy schema differs from baseline: " + ", ".join(changed))
    return baseline["revision"]
