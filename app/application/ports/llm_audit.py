from typing import Protocol

from app.contracts.audit import LlmAudit


class LlmAuditSink(Protocol):
    def append(self, event: LlmAudit) -> None: ...
