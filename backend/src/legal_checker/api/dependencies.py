"""Build dependencies once and expose them to API requests."""

from dataclasses import dataclass, replace
from datetime import timedelta
from functools import lru_cache

from fastapi import Request

from legal_checker.core.config import Settings
from legal_checker.modules.accounts.repository import UserRepository
from legal_checker.modules.accounts.security import SessionSigner
from legal_checker.modules.assessments.cases import CaseRepository, DeploymentCatalog
from legal_checker.modules.assessments.contracts import ContractRepository
from legal_checker.modules.assessments.interfaces import AssessmentStore
from legal_checker.modules.assessments.repository import Store
from legal_checker.modules.assessments.runs import RunRepository
from legal_checker.modules.assessments.service import AssessmentService
from legal_checker.modules.compliance.verification import (
    CriterionVerificationProvider,
    EvidenceRegistryProvider,
)
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.modules.reports.repository import PostgresReportStore, ReportStore
from legal_checker.modules.reviews.repository import ReviewRepository
from legal_checker.shared.llm.audit import LlmAuditSink, PostgresLlmAuditSink
from legal_checker.shared.storage.http import CachedHttpSourceStorage
from legal_checker.shared.storage.source import SourceStorage
from legal_checker.shared.storage.uploads import LocalUploadStorage, RoutingSourceStorage
from legal_checker.workflows.runner import (
    AssessmentRunner,
    ModuleSource,
    ReferenceReplaySource,
    UnconfiguredModules,
)


@dataclass(frozen=True)
class Services:
    """The application's ready-to-use dependencies, rather than business modules."""

    knowledge: KnowledgeSnapshot
    assessments: AssessmentStore
    llm_audit: LlmAuditSink | None = None
    source_storage: SourceStorage | None = None
    settings: Settings | None = None
    cases: CaseRepository | None = None
    reports: ReportStore | None = None
    runner: AssessmentRunner | None = None
    assessment_service: AssessmentService | None = None
    contracts: ContractRepository | None = None
    uploads: LocalUploadStorage | None = None
    # Reads uploaded (upload://) and HTTP(S) sources; source_storage stays HTTP-only.
    document_sources: SourceStorage | None = None
    deployments: DeploymentCatalog | None = None
    users: UserRepository | None = None
    sessions: SessionSigner | None = None  # None when AUTH_MODE=off


def session_signer(settings: Settings) -> SessionSigner | None:
    if settings.auth_mode == "off":
        return None
    if settings.auth_mode != "on":
        raise ValueError(f"Unknown AUTH_MODE={settings.auth_mode!r}")
    if not settings.auth_secret:
        raise ValueError("AUTH_MODE=on needs AUTH_SECRET (at least 32 random characters)")
    return SessionSigner(settings.auth_secret, settings.auth_session_hours * 3600)


def llm_client_factory(settings: Settings):
    """C07 calls are opt-in: ASSESSMENT_LLM=offline, openai, groq, or ollama."""
    if settings.assessment_llm == "offline":
        return None
    if settings.assessment_llm == "ollama":

        def build_ollama():
            from legal_checker.shared.llm.ollama_client import (
                OllamaComplianceClient,
                OllamaComplianceSettings,
            )

            return OllamaComplianceClient(
                OllamaComplianceSettings(
                    base_url=settings.c07_ollama_url,
                    model=settings.c07_ollama_model,
                    timeout_seconds=settings.c07_llm_timeout_seconds,
                    context_tokens=settings.c07_ollama_context_tokens,
                    max_output_tokens=settings.c07_llm_max_output_tokens,
                    threads=settings.c07_ollama_num_threads,
                ),
                PostgresLlmAuditSink(settings.database_url),
            )

        return build_ollama
    if settings.assessment_llm not in {"openai", "groq"}:
        raise ValueError(f"Unknown ASSESSMENT_LLM={settings.assessment_llm!r}")

    def build():
        from legal_checker.shared.llm.client import OpenAIResponsesClient
        from legal_checker.shared.llm.config import OpenAISettings

        return OpenAIResponsesClient(
            OpenAISettings.from_env(), PostgresLlmAuditSink(settings.database_url)
        )

    return build


def document_semantic_extractor(settings: Settings):
    """Documents provider selection remains independent of the C07 workflow."""
    if settings.documents_extractor == "rules":
        return None
    if settings.documents_extractor != "hybrid":
        raise ValueError("DOCUMENTS_EXTRACTOR must be rules or hybrid")
    from legal_checker.modules.documents.ollama_client import OllamaDocumentClient, OllamaOptions
    from legal_checker.modules.documents.semantic_extractor import (
        SemanticDocumentExtractor,
        SemanticOptions,
    )

    audit = PostgresLlmAuditSink(settings.database_url)
    if settings.documents_llm_provider == "openai":
        from legal_checker.modules.documents.openai_client import OpenAIDocumentClient
        from legal_checker.shared.llm.config import OpenAISettings

        client = OpenAIDocumentClient(
            replace(
                OpenAISettings.from_env(),
                timeout_seconds=min(settings.documents_llm_timeout_seconds, 300),
                max_output_tokens=1600,
            ),
            audit,
        )
    elif settings.documents_llm_provider == "ollama":
        client = OllamaDocumentClient(
            OllamaOptions(
                base_url=settings.documents_ollama_url,
                model=settings.documents_ollama_model,
                timeout_seconds=settings.documents_llm_timeout_seconds,
            ),
            audit,
        )
    else:
        raise ValueError("DOCUMENTS_LLM_PROVIDER must be ollama or openai")
    return SemanticDocumentExtractor(
        client,
        settings.source_cache_dir / "documents_llm",
        SemanticOptions(
            max_calls=settings.documents_llm_max_calls,
            recheck_existing=settings.documents_llm_recheck_existing,
        ),
    )


def recommendation_personalizer(settings: Settings):
    """Opt-in C11 phrasing with source validation, independent of C07 reasoning."""
    if settings.c11_personalization == "off":
        return None
    if settings.c11_personalization not in {"ollama", "openai"}:
        raise ValueError("C11_PERSONALIZATION must be off, ollama or openai")
    from legal_checker.modules.recommendations.personalization import (
        C11OllamaOptions,
        C11PersonalizationOptions,
        OllamaRecommendationClient,
        RecommendationPersonalizationService,
    )

    audit = PostgresLlmAuditSink(settings.database_url)
    if settings.c11_personalization == "openai":
        from legal_checker.modules.recommendations.personalization.openai_client import (
            OpenAIRecommendationClient,
        )
        from legal_checker.shared.llm.config import OpenAISettings

        client = OpenAIRecommendationClient(
            replace(
                OpenAISettings.from_env(),
                timeout_seconds=min(settings.c11_llm_timeout_seconds, 300),
                max_output_tokens=settings.c11_llm_output_tokens,
            ),
            audit,
        )
    else:
        client = OllamaRecommendationClient(
            C11OllamaOptions(
                base_url=settings.c11_ollama_url,
                model=settings.c11_ollama_model,
                timeout_seconds=settings.c11_llm_timeout_seconds,
                context_tokens=settings.c11_llm_context_tokens,
                output_tokens=settings.c11_llm_output_tokens,
                threads=settings.c11_llm_num_threads,
            ),
            audit,
        )
    return RecommendationPersonalizationService(
        client,
        C11PersonalizationOptions(
            mode=settings.c11_personalization,
            max_calls=settings.c11_llm_max_calls,
            max_input_chars=settings.c11_llm_max_input_chars,
            total_budget_seconds=settings.c11_llm_total_budget_seconds,
        ),
    )


def module_source(
    settings: Settings,
    cases: CaseRepository,
    documents: SourceStorage | None = None,
    *,
    verification_provider: CriterionVerificationProvider | None = None,
    external_registry_provider: EvidenceRegistryProvider | None = None,
) -> ModuleSource:
    if settings.assessment_modules in {"modules", "modules_di_reference"}:
        from legal_checker.modules.compliance.source_verifier import (
            SourceFactVerifier,
            SyntheticScenarioEvidence,
        )
        from legal_checker.modules.documents.ocr import build_ocr_engine
        from legal_checker.workflows.integrated import IntegratedModulesSource

        if verification_provider is None:
            if settings.synthetic_scenario_path:
                synthetic = SyntheticScenarioEvidence(
                    settings.synthetic_scenario_path,
                    artifact_dir=settings.source_cache_dir / "evidence",
                )
                verification_provider = synthetic
                if external_registry_provider is None:
                    external_registry_provider = synthetic
            else:
                verification_provider = SourceFactVerifier()

        return IntegratedModulesSource(
            settings.database_url,
            cases,
            storage=documents,
            upload_dir=settings.upload_dir,
            source_cache_dir=settings.source_cache_dir,
            llm_client_factory=llm_client_factory(settings),
            llm_max_calls=settings.assessment_llm_max_calls,
            llm_batch_size=settings.assessment_llm_batch_size,
            llm_max_context_chars=settings.assessment_llm_max_context_chars,
            full_document_review=settings.assessment_full_document_review,
            allow_reference_documents=settings.assessment_modules == "modules_di_reference",
            verification_provider=verification_provider,
            external_registry_provider=external_registry_provider,
            document_semantic_extractor=document_semantic_extractor(settings),
            recommendation_personalizer=recommendation_personalizer(settings),
            llm_parallel=settings.assessment_llm_parallel,
            llm_agreement=settings.assessment_llm_agreement,
            llm_hints=settings.assessment_llm_hints,
            ocr=build_ocr_engine(
                settings.document_ocr,
                command=settings.tesseract_cmd,
                language=settings.ocr_language,
                tessdata_dir=settings.tessdata_dir,
            ),
        )
    if settings.assessment_modules == "reference":
        return ReferenceReplaySource(settings.database_url)
    if settings.assessment_modules == "none":
        return UnconfiguredModules()
    raise ValueError(f"Unknown ASSESSMENT_MODULES={settings.assessment_modules!r}")


def build_services(
    settings: Settings,
    *,
    verification_provider: CriterionVerificationProvider | None = None,
    external_registry_provider: EvidenceRegistryProvider | None = None,
) -> Services:
    """Read PostgreSQL knowledge and persist all run results in the same local DB."""
    knowledge = Knowledge(settings.database_url, settings.knowledge_snapshot_sha256)
    assessment_store = Store(settings.database_url)
    cases = CaseRepository(settings.database_url)
    runs = RunRepository(settings.database_url)
    reports = PostgresReportStore(settings.database_url)
    remote_sources = CachedHttpSourceStorage(
        settings.source_cache_dir,
        timeout_seconds=settings.source_download_timeout_seconds,
        max_bytes=settings.source_max_bytes,
    )
    uploads = LocalUploadStorage(settings.upload_dir, max_bytes=settings.source_max_bytes)
    document_sources = RoutingSourceStorage(uploads, remote_sources)
    source = module_source(
        settings,
        cases,
        document_sources,
        verification_provider=verification_provider,
        external_registry_provider=external_registry_provider,
    )
    runner = AssessmentRunner(
        runs=runs,
        reports=reports,
        knowledge=knowledge,
        source=source,
        lease=timedelta(seconds=settings.run_lease_seconds),
    )
    if settings.assessment_queue == "celery":
        from legal_checker.worker.queues import CeleryQueue

        queue = CeleryQueue()
    elif settings.assessment_queue == "inline":
        from legal_checker.worker.queues import InlineQueue

        queue = InlineQueue(runner)
    else:
        raise ValueError(f"Unknown ASSESSMENT_QUEUE={settings.assessment_queue!r}")

    return Services(
        knowledge=knowledge,
        assessments=assessment_store,
        llm_audit=PostgresLlmAuditSink(settings.database_url),
        source_storage=remote_sources,
        settings=settings,
        cases=cases,
        reports=reports,
        runner=runner,
        assessment_service=AssessmentService(
            cases=cases,
            runs=runs,
            reports=reports,
            knowledge=knowledge,
            queue=queue,
            # Per-case label when the source decides it (group A vs dataset reference).
            module_source=getattr(source, "label", source.name),
            reviews=ReviewRepository(settings.database_url),
        ),
        contracts=ContractRepository(settings.database_url),
        uploads=uploads,
        document_sources=document_sources,
        deployments=DeploymentCatalog(
            settings.database_url,
            rule_version=settings.deployment_rule_version,
            legal_knowledge_version=settings.deployment_legal_knowledge_version,
        ),
        users=UserRepository(settings.database_url),
        sessions=session_signer(settings),
    )


def get_services(request: Request) -> Services:
    return request.app.state.services


@lru_cache(maxsize=4)
def _stored_knowledge(database_url: str, sha256: str) -> KnowledgeSnapshot:
    return Knowledge(database_url, sha256)


def knowledge_snapshot(services: Services, sha256: str) -> KnowledgeSnapshot:
    """The exact snapshot a run/report pinned; the current one when it matches."""
    if services.knowledge.sha256 == sha256:
        return services.knowledge
    return _stored_knowledge(services.settings.database_url, sha256)
