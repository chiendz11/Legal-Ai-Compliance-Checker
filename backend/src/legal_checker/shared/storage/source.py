"""Read original source bytes independently of PDF/DOCX parsing."""

from typing import Protocol

from legal_checker.shared.contracts.assessment import SourceDocument


class SourceStorage(Protocol):
    def read(self, source: SourceDocument) -> bytes: ...
