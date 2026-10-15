"""Frozen QA reference tables."""

from importlib.resources import files

from alembic import op

revision = "0003_qa"
down_revision = "0002_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = files("legal_checker.migrations").joinpath("sql/003_evaluation_workbook.sql")
    op.get_bind().exec_driver_sql(
        source.read_text(encoding="utf-8"), execution_options={"no_parameters": True}
    )


def downgrade() -> None:
    raise NotImplementedError("Initial baseline is forward-only; restore a backup to undo it")
