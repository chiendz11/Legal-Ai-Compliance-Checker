from typing import Protocol

from legal_checker.shared.contracts.audit import LlmAudit


class LlmAuditSink(Protocol):
    def append(self, event: LlmAudit) -> None: ...
