"""Compose real modules for one pinned run; QA DI requires an explicit dev mode.

modules reads upload/cache/HTTP bytes and persists extraction before consumers.
modules_di_reference may use frozen DI when bytes are not local, with a distinct label.
C07 verification and external source registration are separately injected trust boundaries.
"""

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

from legal_checker.modules.applicable_law.scope_resolver import CatalogScopeResolver
from legal_checker.modules.applicable_law.temporal_resolver import CatalogTemporalResolver
from legal_checker.modules.assessments.cases import CaseRepository
from legal_checker.modules.citation_validation.service import CatalogCitationValidator
from legal_checker.modules.compliance.content_verifier import admit_content, content_candidates
from legal_checker.modules.compliance.document_review import FullDocumentReviewer
from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
from legal_checker.modules.compliance.review_admission import admit_document_decisions
from legal_checker.modules.compliance.verification import (
    CriterionVerificationProvider,
    EvidenceRegistryProvider,
)
from legal_checker.modules.documents.parser import UnsupportedDocumentError
from legal_checker.modules.documents.repository import DocumentRepository
from legal_checker.modules.documents.semantic_extractor import SemanticDocumentExtractor
from legal_checker.modules.documents.service import PdfDocumentIntelligence, SourceMismatchError
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.modules.retrieval.coverage import add_review_candidates
from legal_checker.modules.retrieval.repository import RetrievalDatasetRepository
from legal_checker.modules.retrieval.service import LexicalRetrievalService
from legal_checker.shared.contracts.assessment import AssessmentCase, SourceDocument
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import DocumentReadCoverage
from legal_checker.shared.contracts.reasoning import (
    ExternalEvidenceRegistration,
    Observation,
    ReasoningRequest,
)
from legal_checker.shared.llm.types import LlmClientError
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
        document_semantic_extractor: SemanticDocumentExtractor | None = None,
        upload_dir: Path | None = None,
        source_cache_dir: Path | None = None,
        llm_client_factory: Callable[[], object] | None = None,
        llm_max_calls: int = 0,
        llm_batch_size: int = 1,
        llm_max_context_chars: int = 80000,
        full_document_review: bool = False,
        allow_reference_documents: bool = False,
        verification_provider: CriterionVerificationProvider | None = None,
        external_registry_provider: EvidenceRegistryProvider | None = None,
    ):
        self.database_url = database_url
        self.cases = cases
        self.storage = storage
        self.document_semantic_extractor = document_semantic_extractor
        self.upload_dir = upload_dir
        self.source_cache_dir = source_cache_dir
        self.llm_client_factory = llm_client_factory
        self.llm_max_calls = llm_max_calls
        self.llm_batch_size = llm_batch_size
        self.llm_max_context_chars = llm_max_context_chars
        self.full_document_review = full_document_review
        self.allow_reference_documents = allow_reference_documents
        self.verification_provider = verification_provider
        self.external_registry_provider = external_registry_provider

    def has_local_bytes(self, source: SourceDocument) -> bool:
        """The exact source is on this server, so reading it needs no network."""
        if self.storage is None:
            return False
        if source.object_uri and source.object_uri.startswith(UPLOAD_SCHEME):
            name = source.object_uri.removeprefix(UPLOAD_SCHEME)
            return self.upload_dir is not None and (self.upload_dir / name).is_file()
        cache = self.source_cache_dir
        return cache is not None and (cache / source.sha256).is_file()

    def label(self, case: AssessmentCase) -> str:
        """Which step 1–2 implementation this case's run will use (recorded on the run)."""
        return (
            REFERENCE_DI_SOURCE
            if self.allow_reference_documents and not self.has_local_bytes(case.source)
            else MODULE_SOURCE
        )

    def _extract(self, case: AssessmentCase, *, context: Context | None = None):
        if self.storage is None:
            raise DocumentReadError(
                "DOCUMENT_INTELLIGENCE_UNAVAILABLE", "Source storage is not configured"
            )
        try:
            extraction = PdfDocumentIntelligence(
                self.storage, semantic=self.document_semantic_extractor
            ).run(case, context=context)
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
        DocumentRepository(self.database_url).save(extraction)
        return extraction

    def _reference(self, case: AssessmentCase):
        # Development-only mode; a production modules run never imports QA loaders.
        from devtools.upstream_fixtures import load_document

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
        if self.allow_reference_documents and not self.has_local_bytes(case.source):
            return self._reference(case)
        return self._extract(case).result

    def prepare(self, context: Context):
        row = self.cases.get(context.ca_id)
        if row is None:
            raise LookupError(f"Case {context.ca_id} not found")
        case = row.case
        verification_provider = self.verification_provider
        external_registry_provider = self.external_registry_provider
        if case.assessment_context.review_mode == "DRAFT_REVIEW":
            from legal_checker.modules.compliance.source_verifier import (
                SourceFactVerifier,
                SyntheticScenarioEvidence,
            )

            if verification_provider is None or isinstance(
                verification_provider, SyntheticScenarioEvidence
            ):
                verification_provider = SourceFactVerifier()
            if isinstance(external_registry_provider, SyntheticScenarioEvidence):
                external_registry_provider = None
        repository = RetrievalDatasetRepository(self.database_url)
        client = self.llm_client_factory() if self.llm_client_factory else None
        registry_candidates = (
            [
                ExternalEvidenceRegistration.model_validate(row.model_dump())
                for row in external_registry_provider.load(
                    context, case, Knowledge(self.database_url, context.knowledge_snapshot_sha256)
                )
            ]
            if external_registry_provider is not None
            else []
        )
        for row in registry_candidates:
            if row.hop_dong_id != case.hop_dong_id or any(
                getattr(row, key) != getattr(context, key)
                for key in Context.model_fields
                if key != "trace_id"
            ):
                raise ValueError("External evidence registry case/run/snapshot/contract mismatch")
        registry: list[ExternalEvidenceRegistration] = []
        active_chunks: set[str] = set()
        diagnostics: list[dict] = []
        read_coverage: DocumentReadCoverage | None = None

        def extract(item):
            nonlocal read_coverage
            if self.allow_reference_documents and not self.has_local_bytes(item.source):
                result = self._reference(item)
                diagnostics.append({"module": "C02", "code": "REFERENCE_DOCUMENT_USED"})
            else:
                extraction = self._extract(item, context=context)
                diagnostics.extend({"module": "C02", **d} for d in extraction.semantic_diagnostics)
                result = extraction.result
                read_coverage = DocumentReadCoverage(
                    hop_dong_id=item.hop_dong_id,
                    source_sha256=item.source.sha256,
                    extraction_version=extraction.version,
                    page_count=len(extraction.document.pages),
                    unreadable_pages=extraction.unreadable_pages,
                )
                diagnostics.append(
                    {
                        "module": "C02",
                        "code": "DOCUMENT_EXTRACTION_PERSISTED",
                        "source_sha256": item.source.sha256,
                        "extraction_version": extraction.version,
                        "parser_version": extraction.parser_version,
                        "unreadable_pages": extraction.unreadable_pages,
                    }
                )
            active_chunks.update(chunk.doan_id for chunk in result.chunks)
            return result

        def section_paths(contract_id):
            return {
                key: value
                for key, value in repository.section_paths(contract_id).items()
                if key in active_chunks
            }

        def fact_evidence(contract_id):
            from legal_checker.modules.retrieval.fact_evidence import FactEvidence

            return [
                FactEvidence(
                    row.ten_truong, tuple(key for key in row.doan_ids if key in active_chunks)
                )
                for row in repository.fact_evidence(contract_id)
                if any(key in active_chunks for key in row.doan_ids)
            ]

        prepared = {}

        def refine(ctx, profile, requirements, retrieval, chunks, knowledge):
            owners = {
                (r.yeu_cau_ca_id, c["tieu_chi_id"])
                for r in requirements
                if r.requirement_version_id
                for c in knowledge.criteria_for(r.requirement_version_id)
            }
            registry[:] = [
                r for r in registry_candidates if (r.yeu_cau_ca_id, r.tieu_chi_id) in owners
            ]
            diagnostic = getattr(verification_provider, "diagnostic", None)
            if diagnostic:
                item = diagnostic(case.source.sha256, knowledge)
                if item:
                    diagnostics.append(item)
            verifications = []
            if verification_provider is not None:
                verifications = verification_provider.verify(
                    ctx,
                    profile,
                    requirements,
                    chunks,
                    knowledge,
                    coverage=read_coverage.model_copy(deep=True) if read_coverage else None,
                )
            else:
                diagnostics.append(
                    {"module": "C07", "code": "VERIFICATION_PROVIDER_NOT_CONFIGURED"}
                )
            prepared["verifications"] = verifications
            retrieval = add_review_candidates(
                ctx,
                requirements,
                chunks,
                retrieval,
                content_candidates(profile, requirements, chunks, knowledge),
                knowledge,
                review_sha256=read_coverage.source_sha256 if read_coverage else "REFERENCE",
                retrieval_version="VERIFIED_CONTENT_BINDING_V1",
                score_key="verified_content_binding",
            )
            content_request = ReasoningRequest(
                **ctx.model_dump(),
                payload={
                    "hop_dong_id": profile.hop_dong_id,
                    "requirements": requirements,
                    "retrieval": retrieval,
                    "chunks": chunks,
                    "external_evidence_registry": registry,
                },
            )
            prepared["content_observations"] = admit_content(
                content_request, profile, knowledge, verifications
            )
            completed_content = {o.tieu_chi_id for o in prepared["content_observations"]}
            if completed_content:
                diagnostics.append(
                    {
                        "module": "C07",
                        "code": "EXACT_CONTENT_VERIFIED",
                        "criterion_ids": sorted(completed_content),
                    }
                )
            if self.full_document_review and client and self.source_cache_dir:
                reviewer = FullDocumentReviewer(
                    client, self.source_cache_dir / "evidence", max_calls=self.llm_max_calls
                )
                try:
                    bundle = reviewer.review(
                        ctx,
                        profile,
                        requirements,
                        chunks,
                        knowledge,
                        verifications,
                        read_coverage,
                        skip_criterion_ids=completed_content,
                    )
                except LlmClientError as error:
                    diagnostics.append({"module": "C07", "code": error.code})
                    bundle = None
                prepared["review_cost"] = reviewer.cost
                if bundle:
                    registry.extend(bundle.registrations)
                    updated = {v.tieu_chi_id: v for v in bundle.verifications}
                    prepared["verifications"] = [
                        updated.get(v.tieu_chi_id, v) for v in verifications
                    ]
                    prepared["review"] = bundle
                    diagnostics.append(bundle.diagnostic)
                    retrieval = add_review_candidates(
                        ctx,
                        requirements,
                        chunks,
                        retrieval,
                        bundle.candidates,
                        knowledge,
                        review_sha256=bundle.diagnostic["artifact_sha256"],
                    )
            return retrieval

        def analyze(ctx, profile, requirements, retrieval, chunks, knowledge):
            if "verifications" not in prepared:
                raise ValueError("Retrieval refinement must prepare verifications before C07")
            verifications = prepared["verifications"]
            request = ReasoningRequest(
                **ctx.model_dump(),
                payload={
                    "hop_dong_id": profile.hop_dong_id,
                    "requirements": requirements,
                    "retrieval": retrieval,
                    "chunks": chunks,
                    "external_evidence_registry": registry,
                },
            )
            document_observations = list(prepared.get("content_observations", []))
            bundle = prepared.get("review")
            if bundle:
                document_observations.extend(
                    admit_document_decisions(
                        request,
                        knowledge,
                        bundle.decisions,
                        verifications,
                        model_version="+".join(bundle.artifact.model_versions),
                        prompt_version=bundle.artifact.prompt_version,
                    )
                )
            visual = {
                v.tieu_chi_id: {
                    "assessment": "ABSENT",
                    "candidate_ids": [],
                    "evidence_id": v.external_excerpts[0].bang_chung_id,
                    "explanation": v.external_excerpts[0].text,
                }
                for v in verifications
                if v.facts.get("visual_absence_reviewed") and v.external_excerpts
            }
            if visual:
                document_observations.extend(
                    admit_document_decisions(
                        request,
                        knowledge,
                        visual,
                        verifications,
                        model_version="SOURCE_PINNED_VISUAL_REVIEW",
                        prompt_version="VISUAL_SOURCE_INSPECTION_20261108",
                    )
                )
                diagnostics.append(
                    {
                        "module": "C07",
                        "code": "PINNED_VISUAL_REVIEW_USED",
                        "criterion_ids": sorted(visual),
                    }
                )
            completed = {v.tieu_chi_id for v in document_observations}
            from legal_checker.modules.compliance.review_scope import OUTSIDE, scope_receipt

            outside_ids = set()
            deferred = []
            records = {v.tieu_chi_id: v for v in verifications}
            for requirement in requirements:
                receipt = scope_receipt(
                    requirement, ctx, knowledge, contract_id=profile.hop_dong_id
                )
                if receipt:
                    outside_ids.update(
                        k for k, v in receipt["criterion_targets"].items() if v == OUTSIDE
                    )
                    if requirement.version_status == "RESOLVED":
                        for criterion in knowledge.criteria_for(requirement.requirement_version_id):
                            key = criterion["tieu_chi_id"]
                            if key in completed or key in outside_ids:
                                continue
                            record = records.get(key)
                            reason = None
                            if not requirement.confirmed:
                                reason = "UPSTREAM_SCOPE_UNRESOLVED: " + "; ".join(
                                    requirement.reason.values()
                                )
                            elif receipt["criterion_targets"].get(key) == "UNRESOLVED_BINDING":
                                reason = (
                                    "CRITERION_BINDING_REQUIRED: "
                                    "local conditions need a registered adapter"
                                )
                            if reason:
                                deferred.append(
                                    Observation(
                                        tieu_chi_id=key,
                                        proposed_finding="UNKNOWN",
                                        giai_thich=reason,
                                        gates=record.gates if record else {},
                                        facts=record.facts if record else {},
                                        facts_verified=record.facts_verified if record else False,
                                        model_version="BACKEND_SCOPE_CHECK_V1",
                                        prompt_version="NOT_USED",
                                    )
                                )
            if outside_ids:
                diagnostics.append(
                    {
                        "module": "C07",
                        "code": "DRAFT_REVIEW_SCOPE",
                        "policy": "DRAFT_CONTENT_REVIEW_V1",
                        "outside_criterion_ids": sorted(outside_ids),
                    }
                )
            remaining = (
                {
                    c["tieu_chi_id"]
                    for r in requirements
                    if r.version_status == "RESOLVED" and r.requirement_version_id
                    for c in knowledge.criteria_for(r.requirement_version_id)
                }
                - completed
                - outside_ids
                - {o.tieu_chi_id for o in deferred}
            )
            provider = LLMObservationProvider(
                client=client,
                max_calls=max(0, self.llm_max_calls - prepared.get("review_cost", 0))
                if client
                else 0,
                automatic_draft_review=True,
                verify_adverse_evidence=True,
                verifications=verifications,
                batch_size=self.llm_batch_size,
                max_context_chars=self.llm_max_context_chars,
                repair_invalid_batches=True,
                criterion_ids=sorted(remaining),
            )
            batch = provider.analyze(
                request,
                knowledge,
                profile=profile,
            )
            diagnostics.extend(
                {"module": "C07", "code": row.error_code, "subject_id": row.tieu_chi_id}
                for row in batch.analyses
                if row.error_code and row.tieu_chi_id in remaining
            )
            return (
                document_observations
                + deferred
                + [v for v in batch.observations if v.tieu_chi_id in remaining]
            )

        def observe(ctx, profile, requirements, retrieval, chunks, knowledge):
            try:
                return analyze(ctx, profile, requirements, retrieval, chunks, knowledge)
            finally:
                close = getattr(client, "close", None)
                if close:
                    close()

        modules = DraftModules(
            intake=SimpleNamespace(register=lambda item: item),
            documents=SimpleNamespace(extract=extract),
            scope=CatalogScopeResolver(),
            temporal=CatalogTemporalResolver(case=case),
            retrieval=LexicalRetrievalService(
                section_paths=section_paths, fact_evidence=fact_evidence
            ),
            citations=CatalogCitationValidator(),
            observations=SimpleNamespace(observe=observe),
            diagnostics=diagnostics,
            external_evidence_registry=registry,
            retrieval_refinement=SimpleNamespace(refine=refine),
        )
        # None keeps the workflow's default steps 5–7 (group C's evaluate).
        return case, modules, None
