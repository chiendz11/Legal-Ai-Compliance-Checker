"""Storage and PDF/DOCX/OCR adapters preserve page text and source hashes."""

from dataclasses import dataclass
from typing import Literal, Protocol

from app.contracts.assessment import SourceDocument


@dataclass(frozen=True)
class DocumentPage:
    page_number: int
    text: str
    method: Literal["TEXT", "OCR"]
    readable: bool


@dataclass(frozen=True)
class DocumentText:
    source_sha256: str
    pages: tuple[DocumentPage, ...]


class SourceStorage(Protocol):
    def read(self, source: SourceDocument) -> bytes: ...


class DocumentReader(Protocol):
    def extract(self, content: bytes, mime_type: str) -> DocumentText: ...
