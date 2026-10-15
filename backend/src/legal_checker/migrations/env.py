"""Alembic online environment; no application startup or workbook loading."""

from alembic import command, context
from alembic.script import ScriptDirectory

from legal_checker.core.config import Settings
from legal_checker.migrations.manager import checked_legacy_revision, migration_engine

config = context.config


def run(connection):
    cli_command = getattr(getattr(config, "cmd_opts", None), "cmd", (None,))[0]
    upgrading = (
        config.attributes.get("allow_legacy_adoption", False) or cli_command is command.upgrade
    )
    if upgrading:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(743249)")
        legacy_revision = checked_legacy_revision(connection)
        connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS dev_meta")
    else:
        legacy_revision = None
    context.configure(
        connection=connection,
        target_metadata=None,
        version_table="alembic_version",
        version_table_schema="dev_meta",
        compare_type=True,
    )
    with context.begin_transaction():
        if legacy_revision:
            context.get_context().stamp(ScriptDirectory.from_config(config), legacy_revision)
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError(
        "Use online Alembic migrations against PostgreSQL; offline SQL export is not configured"
    )

provided = config.attributes.get("connection")
if provided is not None:
    run(provided)
else:
    engine = migration_engine(Settings.from_env().database_url)
    try:
        with engine.begin() as connection:
            run(connection)
    finally:
        engine.dispose()
