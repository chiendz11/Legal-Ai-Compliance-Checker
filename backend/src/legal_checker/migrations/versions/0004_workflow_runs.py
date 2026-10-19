"""Full-assessment run state and immutable report versions (step 9 / group D)."""

from importlib.resources import files

from alembic import op

revision = "0004_workflow_runs"
down_revision = "0003_qa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = files("legal_checker.migrations").joinpath("sql/004_workflow_runs_and_reports.sql")
    op.get_bind().exec_driver_sql(
        source.read_text(encoding="utf-8"), execution_options={"no_parameters": True}
    )


def downgrade() -> None:
    op.execute("DROP TABLE runtime.report_versions")
    op.execute("DROP FUNCTION runtime.reject_report_change()")
    op.execute("DROP TABLE runtime.workflow_runs")
