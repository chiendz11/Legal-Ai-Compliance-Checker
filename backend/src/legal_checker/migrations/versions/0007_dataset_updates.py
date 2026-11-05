"""Append-only history for controlled workbook data updates."""

from alembic import op

revision = "0007_dataset_updates"
down_revision = "0006_users_and_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE dev_meta.dataset_updates (
            sequence BIGSERIAL PRIMARY KEY,
            previous_source_sha256 TEXT NOT NULL,
            source_sha256 TEXT UNIQUE NOT NULL,
            knowledge_snapshot_sha256 TEXT NOT NULL
                REFERENCES knowledge.knowledge_snapshots(sha256),
            legal_knowledge_version TEXT NOT NULL,
            summary JSONB NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE FUNCTION dev_meta.reject_dataset_update_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Dataset update history is append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER immutable_dataset_update BEFORE UPDATE OR DELETE
        ON dev_meta.dataset_updates FOR EACH ROW
        EXECUTE FUNCTION dev_meta.reject_dataset_update_change()
    """)


def downgrade() -> None:
    op.execute("DROP TABLE dev_meta.dataset_updates")
    op.execute("DROP FUNCTION dev_meta.reject_dataset_update_change()")
