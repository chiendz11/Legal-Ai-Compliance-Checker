"""Real step 1–7 modules (groups A, B and C) behind the runner's ModuleSource protocol.

Steps 1–2 use group A's PDF document intelligence whenever the contract's exact bytes are on
this server (an uploaded contract, or a source already in the SHA-256 cache); such runs are
recorded as MODULES. Seeded dataset cases whose PDF is only on the remote dataset host fall
back to the case's frozen QA reference (`load_document`) for the contract profile, chunks and
citations, and are recorded as MODULES_DI_REFERENCE. Either way, legal scope, temporal
resolution, citation validation, retrieval, compliance, risks and recommendations are computed
by the modules.

C07 observations call an LLM only when ASSESSMENT_LLM=openai (paid, opt-in). Offline, the
provider returns an explicit UNKNOWN per criterion instead of inventing findings.
"""

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

from devtools.upstream_fixtures import load_document

from legal_checker.modules.applicable_law.scope_resolver import CatalogScopeResolver
from legal_checker.modules.applicable_law.temporal_resolver import CatalogTemporalResolver
from legal_checker.modules.assessments.cases import CaseRepository
from legal_checker.modules.citation_validation.service import CatalogCitationValidator
from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
from legal_checker.modules.documents.parser import UnsupportedDocumentError
from legal_checker.modules.documents.service import PdfDocumentIntelligence, SourceMismatchError
from legal_checker.modules.retrieval.repository import RetrievalDatasetRepository
from legal_checker.modules.retrieval.service import LexicalRetrievalService
from legal_checker.shared.contracts.assessment import AssessmentCase, SourceDocument
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.storage.http import SourceIntegrityError, SourceStorageError
from legal_checker.shared.storage.source import SourceStorage
from legal_checker.shared.storage.uploads import UPLOAD_SCHEME
from legal_checker.workflows.assessment_workflow import DraftModules

MODULE_SOURCE = "MODULES"
REFERENCE_DI_SOURCE = "MODULES_DI_REFERENCE"


class DocumentIntelligenceUnavailable(LookupError):
    """No document-intelligence output for this case (no local bytes and no reference)."""

    reason = "DOCUMENT_INTELLIGENCE_UNAVAILABLE"


class DocumentReadError(ValueError):
    """Group A could not read this contract; `reason` names the cause for the run page."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class IntegratedModulesSource:
    name = MODULE_SOURCE

    def __init__(
        self,
        database_url: str,
        cases: CaseRepository,
        *,
        storage: SourceStorage | None = None,
        upload_dir: Path | None = None,
        source_cache_dir: Path | None = None,
        llm_client_factory: Callable[[], object] | None = None,
        llm_max_calls: int = 0,
    ):
        self.database_url = database_url
        self.cases = cases
        self.storage = storage
        self.upload_dir = upload_dir
        self.source_cache_dir = source_cache_dir
        self.llm_client_factory = llm_client_factory
        self.llm_max_calls = llm_max_calls

    def has_local_bytes(self, source: SourceDocument) -> bool:
        """The exact source is on this server, so reading it needs no network."""
        if self.storage is None:
            return False
        if source.object_uri.startswith(UPLOAD_SCHEME):
            name = source.object_uri.removeprefix(UPLOAD_SCHEME)
            return self.upload_dir is not None and (self.upload_dir / name).is_file()
        cache = self.source_cache_dir
        return cache is not None and (cache / source.sha256).is_file()

    def label(self, case: AssessmentCase) -> str:
        """Which step 1–2 implementation this case's run will use (recorded on the run)."""
        return MODULE_SOURCE if self.has_local_bytes(case.source) else REFERENCE_DI_SOURCE

    def _extract(self, case: AssessmentCase):
        try:
            extraction = PdfDocumentIntelligence(self.storage).run(case)
        except UnsupportedDocumentError as error:
            raise DocumentReadError("DOCUMENT_FORMAT_UNSUPPORTED", str(error)) from error
        except (SourceMismatchError, SourceIntegrityError) as error:
            raise DocumentReadError("SOURCE_INTEGRITY_FAILED", str(error)) from error
        except SourceStorageError as error:
            raise DocumentReadError("DOCUMENT_INTELLIGENCE_UNAVAILABLE", str(error)) from error
        # A scanned PDF has no text layer: without OCR nothing can be read, and assessing an
        # empty document would turn every requirement into a misleading "insufficient".
        if not extraction.result.chunks:
            raise DocumentReadError(
                "DOCUMENT_NOT_READABLE",
                f"No text could be read from {len(extraction.document.pages)} page(s) "
                f"({len(extraction.unreadable_pages)} without a text layer); scanned PDFs "
                "need OCR, which the document module does not have yet",
            )
        return extraction.result

    def _reference(self, case: AssessmentCase):
        try:
            document = load_document(self.database_url, case.ca_id)
        except (LookupError, ValueError) as error:
            raise DocumentIntelligenceUnavailable(
                f"No document intelligence for {case.ca_id}: its source file is not on this "
                "server and the case has no dataset reference document"
            ) from error
        if document.contract_profile.hop_dong_id != case.hop_dong_id:
            raise DocumentIntelligenceUnavailable("Reference document belongs to another contract")
        return document

    def _document(self, case: AssessmentCase):
        if self.has_local_bytes(case.source):
            return self._extract(case)
        return self._reference(case)

    def prepare(self, context: Context):
        row = self.cases.get(context.ca_id)
        if row is None:
            raise LookupError(f"Case {context.ca_id} not found")
        case = row.case
        repository = RetrievalDatasetRepository(self.database_url)
        client = self.llm_client_factory() if self.llm_client_factory else None
        modules = DraftModules(
            intake=SimpleNamespace(register=lambda item: item),
            documents=SimpleNamespace(extract=self._document),
            scope=CatalogScopeResolver(),
            temporal=CatalogTemporalResolver(),
            retrieval=LexicalRetrievalService(
                section_paths=repository.section_paths, fact_evidence=repository.fact_evidence
            ),
            citations=CatalogCitationValidator(),
            observations=LLMObservationProvider(
                client=client, max_calls=self.llm_max_calls if client else 0
            ),
        )
        # None keeps the workflow's default steps 5–7 (group C's evaluate).
        return case, modules, None
