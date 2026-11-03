"""Real step 3–7 modules (groups B and C) behind the runner's ModuleSource protocol.

Steps 1–2 (document intelligence, group A) are not merged yet. Until they are, the contract
profile, chunks and citations come from the case's frozen QA reference (`load_document`),
so runs are recorded as MODULES_DI_REFERENCE: legal scope, temporal resolution, citation
validation, retrieval, compliance, risks and recommendations are computed by the modules;
only the document input is a dataset reference. Uploaded contracts have no reference and
fail at DOCUMENT_INTELLIGENCE until group A's service is wired here.

C07 observations call an LLM only when ASSESSMENT_LLM=openai (paid, opt-in). Offline, the
provider returns an explicit UNKNOWN per criterion instead of inventing findings.
"""

from collections.abc import Callable
from types import SimpleNamespace

from devtools.upstream_fixtures import load_document

from legal_checker.modules.applicable_law.scope_resolver import CatalogScopeResolver
from legal_checker.modules.applicable_law.temporal_resolver import CatalogTemporalResolver
from legal_checker.modules.assessments.cases import CaseRepository
from legal_checker.modules.citation_validation.service import CatalogCitationValidator
from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
from legal_checker.modules.retrieval.repository import RetrievalDatasetRepository
from legal_checker.modules.retrieval.service import LexicalRetrievalService
from legal_checker.shared.contracts.common import Context
from legal_checker.workflows.assessment_workflow import DraftModules

MODULE_SOURCE = "MODULES_DI_REFERENCE"


class DocumentIntelligenceUnavailable(LookupError):
    """No document-intelligence output for this case (group A not merged, no reference)."""

    reason = "DOCUMENT_INTELLIGENCE_UNAVAILABLE"


class IntegratedModulesSource:
    name = MODULE_SOURCE

    def __init__(
        self,
        database_url: str,
        cases: CaseRepository,
        *,
        llm_client_factory: Callable[[], object] | None = None,
        llm_max_calls: int = 0,
    ):
        self.database_url = database_url
        self.cases = cases
        self.llm_client_factory = llm_client_factory
        self.llm_max_calls = llm_max_calls

    def _document(self, case):
        try:
            document = load_document(self.database_url, case.ca_id)
        except (LookupError, ValueError) as error:
            raise DocumentIntelligenceUnavailable(
                f"No document intelligence for {case.ca_id}: group A's parser is not merged and "
                "this case has no dataset reference document"
            ) from error
        if document.contract_profile.hop_dong_id != case.hop_dong_id:
            raise DocumentIntelligenceUnavailable("Reference document belongs to another contract")
        return document

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
