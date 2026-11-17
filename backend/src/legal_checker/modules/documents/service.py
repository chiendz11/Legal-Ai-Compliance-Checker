"""Step 2 / BR-02, BR-19: PDF → chunks + C02 profile + C03 citations, no fabricated values."""

from dataclasses import dataclass, field
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
from legal_checker.modules.documents.semantic_extractor import SemanticDocumentExtractor
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.common import Context
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
    semantic_diagnostics: list[dict] = field(default_factory=list)

    @property
    def unreadable_pages(self) -> list[int]:
        return [p.page_number for p in self.document.pages if not p.readable]


class PdfDocumentIntelligence:
    """DocumentIntelligenceService cho PDF (lớp chữ hoặc OCR) và DOCX."""

    def __init__(
        self,
        storage: SourceStorage,
        reader: PdfTextReader | None = None,
        *,
        semantic: SemanticDocumentExtractor | None = None,
    ) -> None:
        self.storage = storage
        self.reader = reader or PdfTextReader()
        self.semantic = semantic

    def run(self, case: AssessmentCase, *, context: Context | None = None) -> DocumentExtraction:
        content = self.storage.read(case.source)
        document = self.reader.extract(content, case.source.mime_type)
        if document.source_sha256 != case.source.sha256:
            raise SourceMismatchError("Source SHA-256 differs from C01")
        parser_version = self.reader.parser_version or "unknown"
        # Đổi file, parser, chunker hoặc quy tắc trích xuất → version mới → ID mới, nên
        # kết quả cũ trong DB không bị giữ lại âm thầm (writer dùng ON CONFLICT DO NOTHING).
        pipeline = f"{parser_version}|{EXTRACTOR_VERSION}|{PROFILE_EXTRACTOR_VERSION}"
        complete_draft = (
            case.assessment_context.review_mode == "DRAFT_REVIEW"
            and case.assessment_context.document_set_complete
            and all(p.readable and p.text.strip() for p in document.pages)
        )
        pipeline += f"|complete-draft={complete_draft}"
        version = extraction_version(document.source_sha256, pipeline)
        hop_dong_id = case.hop_dong_id

        chunks = chunk_document(document, hop_dong_id=hop_dong_id, version=version)
        citations = extract_citations(chunks, version=version, document=document)
        profile = extract_profile(
            chunks,
            hop_dong_id=hop_dong_id,
            version=version,
            complete_draft_source=complete_draft,
        )
        semantic_result = None
        if self.semantic is not None:
            if context is None or context.ca_id != case.ca_id:
                raise ValueError("Hybrid Documents requires the active case/run context")
            semantic_result = self.semantic.extract(
                chunks, profile, context, source_sha256=document.source_sha256
            )
            # Bind IDs to the actual semantic output, not just a mutable model tag.
            version = extraction_version(
                document.source_sha256, pipeline + "|" + semantic_result.fingerprint
            )
            original_ids = [chunk.doan_id for chunk in chunks]
            chunks = chunk_document(document, hop_dong_id=hop_dong_id, version=version)
            mapping = dict(zip(original_ids, [c.doan_id for c in chunks], strict=True))
            semantic_result.proposals = [
                row.model_copy(update={"source_id": mapping[row.source_id]})
                for row in semantic_result.proposals
            ]
            semantic_result.diagnostics = [
                {
                    **item,
                    **(
                        {"source_id": mapping[item["source_id"]]}
                        if item.get("source_id") in mapping
                        else {}
                    ),
                }
                for item in semantic_result.diagnostics
            ]
            profile = extract_profile(
                chunks,
                hop_dong_id=hop_dong_id,
                version=version,
                complete_draft_source=complete_draft,
            )
            profile = self.semantic.merge(profile, chunks, semantic_result, version)
            citations = extract_citations(chunks, version=version, document=document)
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
            semantic_diagnostics=semantic_result.diagnostics if semantic_result else [],
        )

    def extract(
        self, case: AssessmentCase, *, context: Context | None = None
    ) -> DocumentIntelligenceResult:
        return self.run(case, context=context).result
