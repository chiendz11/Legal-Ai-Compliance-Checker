"""Web users and append-only C12 review events per run (group D)."""

from importlib.resources import files

from alembic import op

revision = "0006_users_and_reviews"
down_revision = "0005_contract_uploads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = files("legal_checker.migrations").joinpath("sql/006_users_and_reviews.sql")
    op.get_bind().exec_driver_sql(
        source.read_text(encoding="utf-8"), execution_options={"no_parameters": True}
    )


def downgrade() -> None:
    op.execute("DROP TABLE runtime.review_events")
    op.execute("DROP FUNCTION runtime.reject_review_change()")
    op.execute("DROP TABLE runtime.app_users")
