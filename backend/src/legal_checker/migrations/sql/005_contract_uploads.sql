-- Who uploaded which contract, so contracts and their cases can be scoped to a tenant.
CREATE TABLE runtime.contract_uploads (
    hop_dong_id TEXT PRIMARY KEY REFERENCES runtime.hop_dong (hop_dong_id),
    tenant_id TEXT NOT NULL,
    uploaded_by TEXT NOT NULL,
    original_filename TEXT,
    size_bytes BIGINT NOT NULL CHECK (size_bytes > 0),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_contract_uploads_tenant ON runtime.contract_uploads (tenant_id, uploaded_at DESC);
