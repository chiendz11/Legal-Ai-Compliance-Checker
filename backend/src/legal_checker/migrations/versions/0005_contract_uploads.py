"""Uploaded-contract ownership (tenant and uploader) for the web upload flow (group D)."""

from importlib.resources import files

from alembic import op

revision = "0005_contract_uploads"
down_revision = "0004_workflow_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = files("legal_checker.migrations").joinpath("sql/005_contract_uploads.sql")
    op.get_bind().exec_driver_sql(
        source.read_text(encoding="utf-8"), execution_options={"no_parameters": True}
    )


def downgrade() -> None:
    op.execute("DROP TABLE runtime.contract_uploads")
