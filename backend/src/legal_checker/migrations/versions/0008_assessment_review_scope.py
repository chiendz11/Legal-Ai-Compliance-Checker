"""Persist caller-selected review purpose; existing cases keep full assessment."""

from alembic import op

revision = "0008_assessment_review_scope"
down_revision = "0007_dataset_updates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE runtime.ca_danh_gia
        ADD COLUMN review_mode TEXT NOT NULL DEFAULT 'FULL_ASSESSMENT'
            CHECK (review_mode IN ('FULL_ASSESSMENT', 'DRAFT_REVIEW')),
        ADD COLUMN document_set_complete BOOLEAN NOT NULL DEFAULT FALSE
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE runtime.ca_danh_gia
        DROP COLUMN document_set_complete, DROP COLUMN review_mode
    """)
