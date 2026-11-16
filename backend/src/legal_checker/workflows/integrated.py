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

import logging
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import psycopg
from devtools.upstream_fixtures import load_document

from legal_checker.modules.applicable_law.scope_resolver import CatalogScopeResolver
from legal_checker.modules.applicable_law.temporal_resolver import CatalogTemporalResolver
from legal_checker.modules.assessments.cases import CaseRepository
from legal_checker.modules.citation_validation.service import CatalogCitationValidator
from legal_checker.modules.compliance.backend_verification import VerifiedObservationProvider
from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
from legal_checker.modules.documents.ocr import OcrEngine, OcrFailedError
from legal_checker.modules.documents.parser import PdfTextReader, UnsupportedDocumentError
from legal_checker.modules.documents.repository import DocumentRepository
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
logger = logging.getLogger(__name__)


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
        llm_parallel: int = 1,
        llm_agreement: int = 1,
        llm_hints: bool = False,
        ocr: OcrEngine | None = None,
    ):
        self.database_url = database_url
        self.ocr = ocr
        self.cases = cases
        self.storage = storage
        self.upload_dir = upload_dir
        self.source_cache_dir = source_cache_dir
        self.llm_client_factory = llm_client_factory
        self.llm_max_calls = llm_max_calls
        self.llm_parallel = llm_parallel
        self.llm_agreement = llm_agreement
        self.llm_hints = llm_hints

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
            extraction = PdfDocumentIntelligence(self.storage, PdfTextReader(self.ocr)).run(case)
        except OcrFailedError as error:
            raise DocumentReadError("OCR_FAILED", str(error)) from error
        except UnsupportedDocumentError as error:
            raise DocumentReadError("DOCUMENT_FORMAT_UNSUPPORTED", str(error)) from error
        except (SourceMismatchError, SourceIntegrityError) as error:
            raise DocumentReadError("SOURCE_INTEGRITY_FAILED", str(error)) from error
        except SourceStorageError as error:
            raise DocumentReadError("DOCUMENT_INTELLIGENCE_UNAVAILABLE", str(error)) from error
        # Assessing an empty document would turn every requirement into a misleading
        # "insufficient", so a contract with no readable text stops here.
        if not extraction.result.chunks:
            pages = len(extraction.document.pages)
            unreadable = len(extraction.unreadable_pages)
            cause = (
                "OCR found no readable text either (blank or very low-quality scan)"
                if self.ocr is not None
                else "OCR is not configured (install Tesseract with Vietnamese data, see "
                "DOCUMENT_OCR in .env.example)"
            )
            raise DocumentReadError(
                "DOCUMENT_NOT_READABLE",
                f"No text could be read from {pages} page(s) ({unreadable} without a text "
                f"layer); {cause}",
            )
        # The rule catalogue only covers apartment sale contracts. A document whose type
        # group A cannot recognise (a resolution, a notice, another kind of contract) would
        # leave every requirement's scope unknown and report all of them as "insufficient",
        # which reads like a finding about the contract. Say plainly that it is not handled.
        if extraction.result.contract_profile.profile.loai_hop_dong_id is None:
            raise DocumentReadError(
                "CONTRACT_TYPE_UNSUPPORTED",
                "The document is not recognised as an apartment sale contract (no "
                "'HỢP ĐỒNG MUA BÁN CĂN HỘ' title was found); only that contract type is "
                "assessed for now",
            )
        # An uploaded contract has no seeded rows, so its chunks (with section paths), field
        # evidence, parties, time markers, citations and profile are stored before retrieval
        # reads them by contract ID. IDs carry the extraction version, so a rerun adds nothing.
        # Seeded contracts keep their reviewed dataset rows untouched.
        # Storing is an aid to retrieval, not part of the assessment itself: if a catalogue
        # row is missing the run still uses the in-memory extraction, and the cause is logged.
        if case.source.object_uri.startswith(UPLOAD_SCHEME):
            try:
                DocumentRepository(self.database_url).save(extraction, replace_profile=True)
            except psycopg.Error as error:
                logger.warning(
                    "document_extraction_not_stored",
                    extra={"hop_dong_id": case.hop_dong_id, "error": str(error)[:300]},
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
            # Backend attestations for contract-content criteria are built from the run's
            # resolved checklist; without them no catalogue criterion can ever conclude.
            observations=VerifiedObservationProvider(
                lambda verifications: LLMObservationProvider(
                    client=client,
                    max_calls=self.llm_max_calls if client else 0,
                    max_parallel_calls=max(1, self.llm_parallel),
                    agreement_calls=max(1, self.llm_agreement),
                    call_unconcludable=self.llm_hints,
                    automatic_draft_review=True,
                    verifications=verifications,
                )
            ),
        )
        # None keeps the workflow's default steps 5–7 (group C's evaluate).
        return case, modules, None
