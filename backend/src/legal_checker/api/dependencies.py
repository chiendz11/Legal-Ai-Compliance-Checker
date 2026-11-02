"""Build dependencies once and expose them to API requests."""

from dataclasses import dataclass
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
    """Paid C07 calls are opt-in: ASSESSMENT_LLM=openai plus OPENAI_API_KEY/OPENAI_MODEL."""
    if settings.assessment_llm == "offline":
        return None
    if settings.assessment_llm != "openai":
        raise ValueError(f"Unknown ASSESSMENT_LLM={settings.assessment_llm!r}")

    def build():
        from legal_checker.shared.llm.client import OpenAIResponsesClient
        from legal_checker.shared.llm.config import OpenAISettings

        return OpenAIResponsesClient(
            OpenAISettings.from_env(), PostgresLlmAuditSink(settings.database_url)
        )

    return build


def module_source(settings: Settings, cases: CaseRepository) -> ModuleSource:
    if settings.assessment_modules == "modules":
        from legal_checker.workflows.integrated import IntegratedModulesSource

        return IntegratedModulesSource(
            settings.database_url,
            cases,
            llm_client_factory=llm_client_factory(settings),
            llm_max_calls=settings.assessment_llm_max_calls,
        )
    if settings.assessment_modules == "reference":
        return ReferenceReplaySource(settings.database_url)
    if settings.assessment_modules == "none":
        return UnconfiguredModules()
    raise ValueError(f"Unknown ASSESSMENT_MODULES={settings.assessment_modules!r}")


def build_services(settings: Settings) -> Services:
    """Read PostgreSQL knowledge and persist all run results in the same local DB."""
    knowledge = Knowledge(settings.database_url, settings.knowledge_snapshot_sha256)
    assessment_store = Store(settings.database_url)
    cases = CaseRepository(settings.database_url)
    runs = RunRepository(settings.database_url)
    reports = PostgresReportStore(settings.database_url)
    source = module_source(settings, cases)
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

    remote_sources = CachedHttpSourceStorage(
        settings.source_cache_dir,
        timeout_seconds=settings.source_download_timeout_seconds,
        max_bytes=settings.source_max_bytes,
    )
    uploads = LocalUploadStorage(settings.upload_dir, max_bytes=settings.source_max_bytes)
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
            module_source=source.name,
            reviews=ReviewRepository(settings.database_url),
        ),
        contracts=ContractRepository(settings.database_url),
        uploads=uploads,
        document_sources=RoutingSourceStorage(uploads, remote_sources),
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
