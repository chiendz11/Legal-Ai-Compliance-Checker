"""Immutable knowledge and run snapshots."""

from importlib.resources import files

from alembic import op

revision = "0002_snapshots"
down_revision = "0001_workbook"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = files("legal_checker.migrations").joinpath("sql/002_snapshots_and_runs.sql")
    op.get_bind().exec_driver_sql(
        source.read_text(encoding="utf-8"), execution_options={"no_parameters": True}
    )


def downgrade() -> None:
    raise NotImplementedError("Initial baseline is forward-only; restore a backup to undo it")
