"""Create the concrete objects shared by API requests.

Settings contains paths. This module opens those data sources and returns objects
that workflows can use through their interfaces. See docs/startup.md.
"""

from dataclasses import dataclass

from app.adapters.database.sqlite import Store
from app.adapters.knowledge_sources.snapshot import Knowledge
from app.shared.config import Settings
from app.workflows.interfaces.assessment_store import AssessmentStore
from app.workflows.interfaces.knowledge import KnowledgeSnapshot


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
