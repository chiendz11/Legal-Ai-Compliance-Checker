"""Build dependencies once and expose them to API requests."""

from dataclasses import dataclass

from fastapi import Request

from legal_checker.core.config import Settings
from legal_checker.modules.assessments.interfaces import AssessmentStore
from legal_checker.modules.assessments.repository import Store
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.shared.llm.audit import LlmAuditSink, PostgresLlmAuditSink
from legal_checker.shared.storage.http import CachedHttpSourceStorage
from legal_checker.shared.storage.source import SourceStorage


@dataclass(frozen=True)
class Services:
    """The application's ready-to-use dependencies, rather than business modules."""

    knowledge: KnowledgeSnapshot
    assessments: AssessmentStore
    llm_audit: LlmAuditSink | None = None
    source_storage: SourceStorage | None = None


def build_services(settings: Settings) -> Services:
    """Read PostgreSQL knowledge and persist all run results in the same local DB."""
    knowledge = Knowledge(settings.database_url, settings.knowledge_snapshot_sha256)
    assessment_store = Store(settings.database_url)

    return Services(
        knowledge=knowledge,
        assessments=assessment_store,
        llm_audit=PostgresLlmAuditSink(settings.database_url),
        source_storage=CachedHttpSourceStorage(
            settings.source_cache_dir,
            timeout_seconds=settings.source_download_timeout_seconds,
            max_bytes=settings.source_max_bytes,
        ),
    )


def get_services(request: Request) -> Services:
    return request.app.state.services
