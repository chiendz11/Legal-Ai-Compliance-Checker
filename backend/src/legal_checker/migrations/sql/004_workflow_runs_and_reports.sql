-- Full-assessment run state (queue/worker progress) and immutable C13 report versions.
CREATE TABLE runtime.workflow_runs (
    ca_id TEXT NOT NULL REFERENCES runtime.ca_danh_gia (ca_id),
    run_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    context_json JSONB NOT NULL,
    module_source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'QUEUED'
        CHECK (status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')),
    stages_json JSONB NOT NULL,
    error_json JSONB,
    draft_json JSONB,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    heartbeat_at TIMESTAMPTZ,
    PRIMARY KEY (ca_id, run_id),
    UNIQUE (ca_id, idempotency_key),
    CHECK ((status = 'COMPLETED') = (draft_json IS NOT NULL))
);
CREATE INDEX ix_workflow_runs_pending ON runtime.workflow_runs (status, updated_at)
    WHERE status IN ('QUEUED', 'RUNNING');

CREATE TABLE runtime.report_versions (
    bao_cao_id TEXT PRIMARY KEY,
    ca_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    version_no INTEGER NOT NULL CHECK (version_no >= 1),
    review_revision TEXT NOT NULL,
    report_json JSONB NOT NULL,
    report_sha256 TEXT NOT NULL CHECK (report_sha256 ~ '^[a-f0-9]{64}$'),
    exports_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ca_id, run_id, version_no),
    FOREIGN KEY (ca_id, run_id) REFERENCES runtime.workflow_runs (ca_id, run_id)
);
-- report_json is immutable; only export URIs may be recorded afterwards.
CREATE FUNCTION runtime.reject_report_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' OR NEW.report_json IS DISTINCT FROM OLD.report_json
       OR NEW.report_sha256 IS DISTINCT FROM OLD.report_sha256
       OR NEW.bao_cao_id IS DISTINCT FROM OLD.bao_cao_id THEN
        RAISE EXCEPTION 'Report versions are immutable; build a new version';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER immutable_report_version BEFORE UPDATE OR DELETE ON runtime.report_versions
    FOR EACH ROW EXECUTE FUNCTION runtime.reject_report_change();
