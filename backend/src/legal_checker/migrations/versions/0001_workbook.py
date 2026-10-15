"""Initial workbook schema and seed import bookkeeping."""

from importlib.resources import files

from alembic import op

revision = "0001_workbook"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = files("legal_checker.migrations").joinpath("sql/001_workbook_v7_4_9.sql")
    op.get_bind().exec_driver_sql(
        source.read_text(encoding="utf-8"), execution_options={"no_parameters": True}
    )
    op.execute("""
        CREATE TABLE dev_meta.seed_imports (
            source_sha256 TEXT PRIMARY KEY, row_counts JSONB NOT NULL,
            imported_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    raise NotImplementedError("Initial baseline is forward-only; restore a backup to undo it")
