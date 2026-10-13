-- Immutable development knowledge snapshots and assessment run lineage.
CREATE TABLE knowledge.knowledge_snapshots (
    sha256 TEXT PRIMARY KEY CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    schema_version TEXT NOT NULL,
    content JSONB NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'DEV_UNVERIFIED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE FUNCTION knowledge.reject_snapshot_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Knowledge snapshot content is immutable; create a new snapshot';
END;
$$;
CREATE TRIGGER immutable_knowledge_snapshot BEFORE UPDATE OR DELETE
    ON knowledge.knowledge_snapshots FOR EACH ROW
    EXECUTE FUNCTION knowledge.reject_snapshot_change();
CREATE TABLE runtime.assessment_case_pins (
    ca_id TEXT PRIMARY KEY REFERENCES runtime.ca_danh_gia (ca_id),
    pin JSONB NOT NULL,
    knowledge_sha256 TEXT NOT NULL REFERENCES knowledge.knowledge_snapshots (sha256)
);
CREATE TABLE runtime.assessment_runs (
    ca_id TEXT NOT NULL REFERENCES runtime.ca_danh_gia (ca_id),
    run_id TEXT NOT NULL,
    input_sha256 TEXT NOT NULL,
    output_sha256 TEXT NOT NULL,
    input_json JSONB NOT NULL,
    response_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (ca_id, run_id)
);
CREATE TABLE runtime.assessment_output_lineage (
    table_name TEXT NOT NULL,
    output_id TEXT NOT NULL,
    ca_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    PRIMARY KEY (table_name, output_id),
    FOREIGN KEY (ca_id, run_id) REFERENCES runtime.assessment_runs (ca_id, run_id)
        DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX ix_output_lineage_run ON runtime.assessment_output_lineage (ca_id, run_id);
