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
    """Load JSON knowledge and prepare SQLite tables once per app instance."""

    # Read the JSON file, calculate its checksum and index criteria/rules in memory.
    knowledge = Knowledge(settings.knowledge_path)

    # Create the DB directory/file and missing tables; existing results are preserved.
    # Store opens a connection for each get/save operation, not a permanent connection.
    assessment_store = Store(settings.database_path)

    # Routes receive these same objects via app.state.services and get_services.
    return Services(knowledge=knowledge, assessments=assessment_store)


def get_services(request: Request) -> Services:
    return request.app.state.services
