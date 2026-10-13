"""Build dependencies once and expose them to API requests."""

from dataclasses import dataclass

from fastapi import Request

from legal_checker.core.config import Settings
from legal_checker.modules.assessments.interfaces import AssessmentStore
from legal_checker.modules.assessments.repository import Store
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.legal_knowledge.repository import Knowledge


@dataclass(frozen=True)
class Services:
    """The application's ready-to-use dependencies, rather than business modules."""

    knowledge: KnowledgeSnapshot
    assessments: AssessmentStore


def build_services(settings: Settings) -> Services:
    """Read PostgreSQL knowledge and persist all run results in the same local DB."""
    knowledge = Knowledge(settings.database_url, settings.knowledge_snapshot_sha256)
    assessment_store = Store(settings.database_url)

    return Services(knowledge=knowledge, assessments=assessment_store)


def get_services(request: Request) -> Services:
    return request.app.state.services
