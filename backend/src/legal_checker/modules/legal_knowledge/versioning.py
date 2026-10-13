"""BO-02, BQ-08 / X01: knowledge review/versioning interface, not an automatic approval."""

from typing import Protocol

from legal_checker.shared.contracts.deployment import DeploymentSnapshot


class KnowledgeCurationService(Protocol):
    def publish_snapshot(
        self, snapshot: DeploymentSnapshot, actor_id: str
    ) -> DeploymentSnapshot: ...
