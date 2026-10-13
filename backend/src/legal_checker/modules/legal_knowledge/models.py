from typing import Any, Protocol


class KnowledgeSnapshot(Protocol):
    """Read-only knowledge contract used by business modules; no storage implementation."""

    sha256: str
    schema_version: str
    tables: dict[str, list[dict[str, Any]]]
    criteria: dict[str, dict[str, Any]]
    versions: dict[str, dict[str, Any]]
    risks: dict[str, dict[str, Any]]
    recommendations: dict[str, dict[str, Any]]
    aggregations: dict[str, dict[str, Any]]
    articles: dict[str, dict[str, Any]]
    documents: dict[str, dict[str, Any]]

    def criteria_for(self, version_id: str | None) -> list[dict[str, Any]]: ...
    def decision(self, criterion_id: str, finding: str) -> dict[str, Any]: ...
    def legal_basis(self, criterion: dict[str, Any]) -> list[str]: ...
