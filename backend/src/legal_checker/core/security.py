"""BRD role/tenant authorization seam. No permissive default implementation is supplied."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Actor:
    """Authenticated caller as derived by the backend; clients never supply these fields."""

    actor_id: str
    tenant_id: str
    roles: frozenset[str] = field(default_factory=frozenset)

    def has(self, role: str) -> bool:
        return role in self.roles


class AccessPolicy(Protocol):
    def require_case_access(self, actor_id: str, tenant_id: str, ca_id: str) -> None: ...
    def require_review_permission(self, actor_id: str, tenant_id: str, ca_id: str) -> None: ...
    def require_knowledge_curator(self, actor_id: str) -> None: ...
