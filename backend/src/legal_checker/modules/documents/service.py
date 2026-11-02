"""Step 2 / BR-02, BR-19: PDF → chunks + C02 profile + C03 citations, no fabricated values."""

from dataclasses import dataclass
from typing import Protocol

from legal_checker.modules.documents.chunker import (
    ChunkRecord,
    chunk_document,
    extraction_version,
)
from legal_checker.modules.documents.citation_extractor import (
    EXTRACTOR_VERSION,
    CitationRecord,
    extract_citations,
)
from legal_checker.modules.documents.parser import DocumentText, PdfTextReader
from legal_checker.modules.documents.profile_extractor import (
    PROFILE_EXTRACTOR_VERSION,
    extract_profile,
)
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.document_intelligence import DocumentIntelligenceResult
from legal_checker.shared.storage.source import SourceStorage
from legal_checker.workflows.handoffs import validate_document


class DocumentIntelligenceService(Protocol):
    def extract(self, case: AssessmentCase) -> DocumentIntelligenceResult: ...


class SourceMismatchError(ValueError):
    """Bytes đọc được không khớp SHA-256 khai báo trong C01: dừng, không trích xuất."""


@dataclass(frozen=True)
class DocumentExtraction:
    """Kết quả đầy đủ cho repository: DTO bàn giao + metadata chỉ dùng khi ghi DB."""

    case: AssessmentCase
    result: DocumentIntelligenceResult
    document: DocumentText
    chunks: list[ChunkRecord]
    citations: list[CitationRecord]
    version: str
    parser_version: str

    @property
    def unreadable_pages(self) -> list[int]:
        return [p.page_number for p in self.document.pages if not p.readable]


class PdfDocumentIntelligence:
    """DocumentIntelligenceService cho PDF có text layer (chưa OCR, chưa DOCX)."""

    def __init__(self, storage: SourceStorage, reader: PdfTextReader | None = None) -> None:
        self.storage = storage
        self.reader = reader or PdfTextReader()

    def run(self, case: AssessmentCase) -> DocumentExtraction:
        content = self.storage.read(case.source)
        document = self.reader.extract(content, case.source.mime_type)
        if document.source_sha256 != case.source.sha256:
            raise SourceMismatchError("Source SHA-256 differs from C01")
        parser_version = self.reader.parser_version or "unknown"
        # Đổi file, parser, chunker hoặc quy tắc trích xuất → version mới → ID mới, nên
        # kết quả cũ trong DB không bị giữ lại âm thầm (writer dùng ON CONFLICT DO NOTHING).
        pipeline = f"{parser_version}|{EXTRACTOR_VERSION}|{PROFILE_EXTRACTOR_VERSION}"
        version = extraction_version(document.source_sha256, pipeline)
        hop_dong_id = case.hop_dong_id

        chunks = chunk_document(document, hop_dong_id=hop_dong_id, version=version)
        citations = extract_citations(chunks, version=version)
        profile = extract_profile(chunks, hop_dong_id=hop_dong_id, version=version)
        result = DocumentIntelligenceResult(
            contract_profile=profile,
            chunks=[c.to_contract() for c in chunks],
            citations=[c.to_contract() for c in citations],
        )
        validate_document(case, result)
        return DocumentExtraction(
            case=case,
            result=result,
            document=document,
            chunks=chunks,
            citations=citations,
            version=version,
            parser_version=parser_version,
        )

    def extract(self, case: AssessmentCase) -> DocumentIntelligenceResult:
        return self.run(case).result
