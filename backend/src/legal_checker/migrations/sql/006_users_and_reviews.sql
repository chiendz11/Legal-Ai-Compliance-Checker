-- Web users (local accounts; tokens are signed sessions, passwords stored as scrypt hashes).
CREATE TABLE runtime.app_users (
    user_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    roles TEXT[] NOT NULL DEFAULT '{}'
        CHECK (roles <@ ARRAY['viewer', 'uploader', 'reviewer', 'publisher']::TEXT[]),
    password_hash TEXT NOT NULL,
    disabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- C12 review events of one run; append-only. Machine outputs are never modified.
CREATE TABLE runtime.review_events (
    review_id TEXT PRIMARY KEY,
    ca_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    seq BIGINT GENERATED ALWAYS AS IDENTITY,
    doi_tuong_loai TEXT NOT NULL,
    doi_tuong_id TEXT NOT NULL,
    target_sha256 TEXT NOT NULL CHECK (target_sha256 ~ '^[a-f0-9]{64}$'),
    action TEXT NOT NULL
        CHECK (action IN ('CONFIRM', 'OVERRIDE', 'REQUEST_MORE_EVIDENCE', 'REJECT', 'COMMENT')),
    before_json JSONB NOT NULL,
    after_json JSONB NOT NULL,
    reason TEXT NOT NULL CHECK (length(reason) > 0),
    actor_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    phien_ban_id TEXT NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (ca_id, run_id) REFERENCES runtime.workflow_runs (ca_id, run_id)
);
CREATE INDEX ix_review_events_run ON runtime.review_events (ca_id, run_id, seq);

CREATE FUNCTION runtime.reject_review_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Review events are append-only; record a new review instead';
END;
$$;
CREATE TRIGGER append_only_review_event BEFORE UPDATE OR DELETE ON runtime.review_events
    FOR EACH ROW EXECUTE FUNCTION runtime.reject_review_change();
