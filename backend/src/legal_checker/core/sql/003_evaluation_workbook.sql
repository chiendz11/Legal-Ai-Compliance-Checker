-- QA inputs/expected references are separate from runtime results.
CREATE SCHEMA qa;
CREATE TABLE qa.case_manifest (
    "case_id" TEXT PRIMARY KEY,
    "hop_dong_id" TEXT,
    "group_id" TEXT,
    "split" TEXT,
    "case_kind" TEXT,
    "label_quality" TEXT,
    "dataset_version" TEXT,
    "label_version" TEXT,
    "knowledge_snapshot_sha256" TEXT,
    "module_scope" TEXT,
    "limitations_json" JSONB,
    CHECK (split IN ('DEV','VALIDATION','TEST','REGRESSION')),
    CHECK (case_kind IN ('CORPUS','CONTROLLED')),
    CHECK (label_quality IN ('SILVER_GUARD_REFERENCE','SYNTHETIC_SPEC'))
 );
CREATE TABLE qa.artifacts (
    "artifact_part_id" TEXT PRIMARY KEY,
    "case_id" TEXT,
    "role" TEXT,
    "contract_name" TEXT,
    "record_id" TEXT,
    "part_number" INTEGER,
    "part_count" INTEGER,
    "payload_sha256" TEXT,
    "content" TEXT,
    CHECK (role IN ('INPUT','EXPECTED','PROPOSAL')),
    CHECK (part_number >= 1 AND part_number <= part_count),
    CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    UNIQUE (case_id, role, contract_name, record_id, part_number),
    FOREIGN KEY (case_id) REFERENCES qa.case_manifest (case_id) DEFERRABLE INITIALLY DEFERRED
 );
CREATE TABLE qa.controlled_assertions (
    "case_id" TEXT PRIMARY KEY,
    "expected_assertions_json" JSONB,
    "rationale" TEXT,
    "legal_review_id" TEXT,
    FOREIGN KEY (case_id) REFERENCES qa.case_manifest (case_id) DEFERRABLE INITIALLY DEFERRED
 );
CREATE TABLE qa.legal_checks (
    "review_id" TEXT PRIMARY KEY,
    "document_number" TEXT,
    "article_scope" TEXT,
    "source_url" TEXT,
    "source_sha256" TEXT,
    "as_of" DATE,
    "review_status" TEXT,
    "finding_summary" TEXT,
    "limitations" TEXT
 );
CREATE TABLE qa.source_checks (
    "tep_id" TEXT PRIMARY KEY,
    "hop_dong_id" TEXT,
    "source_url" TEXT,
    "status" TEXT,
    "download_sha256" TEXT,
    "bytes" INTEGER,
    "error" TEXT
 );
CREATE TABLE qa.change_log (
    "change_id" TEXT PRIMARY KEY,
    "table_name" TEXT,
    "record_id" TEXT,
    "reason" TEXT,
    "before_json" JSONB,
    "after_json" JSONB
 );
CREATE INDEX ix_qa_manifest_split ON qa.case_manifest (split, case_kind);
CREATE INDEX ix_qa_artifact_case ON qa.artifacts (case_id, role, contract_name);
CREATE FUNCTION qa.reject_reference_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'QA reference is frozen; curate a new dataset/label version';
END;
$$;
CREATE TRIGGER immutable_case_manifest BEFORE UPDATE OR DELETE ON qa.case_manifest
    FOR EACH ROW EXECUTE FUNCTION qa.reject_reference_change();
CREATE TRIGGER immutable_qa_artifact BEFORE UPDATE OR DELETE ON qa.artifacts
    FOR EACH ROW EXECUTE FUNCTION qa.reject_reference_change();
CREATE TRIGGER immutable_controlled_assertion BEFORE UPDATE OR DELETE ON qa.controlled_assertions
    FOR EACH ROW EXECUTE FUNCTION qa.reject_reference_change();
