from dataclasses import dataclass

from app.application.ports.assessment_store import AssessmentStore
from app.application.ports.knowledge import KnowledgeSnapshot
from app.core.config import Settings
from app.infrastructure.knowledge.snapshot import Knowledge
from app.infrastructure.persistence.sqlite import Store


@dataclass(frozen=True)
class Services:
    knowledge: KnowledgeSnapshot
    assessments: AssessmentStore


def build_services(settings: Settings) -> Services:
    return Services(
        knowledge=Knowledge(settings.knowledge_path), assessments=Store(settings.database_path)
    )
