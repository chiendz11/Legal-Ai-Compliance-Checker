"""X01: a curated release snapshot; does not silently replace an assessment pin."""

from legal_checker.shared.contracts.common import Model


class DeploymentSnapshot(Model):
    phien_ban_id: str
    schema_version: str
    legal_snapshot_sha256: str
    contract_snapshot_sha256: str
    model_reasoning: str | None = None
    model_embedding: str | None = None
    prompt_version: str | None = None
    rule_version: str
