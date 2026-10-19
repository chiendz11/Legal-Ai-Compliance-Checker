"""Reference replay: stand-in step implementations for integration while A/B/C are unbuilt.

Each step returns the frozen QA EXPECTED output of the same case (role EXPECTED in
qa.artifacts), rebound to the new run ID. It exercises orchestration, persistence, report
and UI wiring only: outputs are dataset references, not results of any module, and runs
using it are recorded with module_source=REFERENCE_REPLAY. Never use it for metrics.
"""

from dataclasses import dataclass
from typing import Any

from devtools.qa_validation import join_artifacts

from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import DocumentIntelligenceResult
from legal_checker.shared.contracts.pipeline import PipelineRequest, PipelineResponse
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.shared.contracts.temporal import ApplicableRequirement
from legal_checker.workflows.assessment_workflow import DraftModules, Evaluator

MODULE_SOURCE = "REFERENCE_REPLAY"

_CONTRACTS = (
    ("INPUT", "DocumentInput"),
    ("INPUT", "PipelineRequest"),
    ("EXPECTED", "DocumentIntelligenceResult"),
    ("EXPECTED", "C04"),
    ("EXPECTED", "C05"),
    ("EXPECTED", "C06"),
    ("EXPECTED", "C09"),
    ("EXPECTED", "PipelineResponse"),
)


class ReferenceUnavailable(LookupError):
    """The case has no complete QA reference to replay."""


def load_reference_payloads(database_url: str, ca_id: str) -> dict[tuple[str, str], Any]:
    with connect_postgres(database_url) as connection:
        rows = connection.execute(
            """SELECT * FROM qa.artifacts
               WHERE case_id=%s AND (role, contract_name) IN
                   (SELECT * FROM unnest(%s::text[], %s::text[]))""",
            (ca_id, [r for r, _ in _CONTRACTS], [c for _, c in _CONTRACTS]),
        ).fetchall()
    grouped: dict[tuple[str, str], list] = {}
    for row in rows:
        grouped.setdefault((row["role"], row["contract_name"]), []).append(row)
    payloads = {}
    for key in _CONTRACTS:
        joined = join_artifacts(grouped.get(key, []))
        if len(joined) != 1:
            raise ReferenceUnavailable(f"Case {ca_id} has no single QA reference for {key}")
        payloads[key] = next(iter(joined.values()))
    return payloads


def _rebind(item: dict, run_id: str) -> dict:
    return {**item, "lan_chay_id": run_id} if "lan_chay_id" in item else item


@dataclass(frozen=True)
class ReferenceReplay:
    """Holds one case's references; build() binds them to the run's context."""

    case: AssessmentCase
    reference_context: Context
    payloads: dict[tuple[str, str], Any]

    @classmethod
    def load(cls, database_url: str, ca_id: str) -> "ReferenceReplay":
        payloads = load_reference_payloads(database_url, ca_id)
        document_input = payloads[("INPUT", "DocumentInput")]
        return cls(
            case=AssessmentCase.model_validate(document_input["case"]),
            reference_context=Context.model_validate(document_input["context"]),
            payloads=payloads,
        )

    def build(self, context: Context) -> tuple[DraftModules, Evaluator]:
        if context.ca_id != self.case.ca_id:
            raise ValueError("Replay context belongs to a different case")
        run_id = context.run_id
        p = self.payloads
        observations = PipelineRequest.model_validate(
            p[("INPUT", "PipelineRequest")]
        ).payload.observations

        class Steps:
            def register(self, case: AssessmentCase) -> AssessmentCase:
                return case

            def extract(self, case: AssessmentCase) -> DocumentIntelligenceResult:
                return DocumentIntelligenceResult.model_validate(
                    p[("EXPECTED", "DocumentIntelligenceResult")]
                )

            def observe(self, *args):
                return [item.model_copy(deep=True) for item in observations]

        class Scope:
            def resolve(self, *args) -> list[ScopeResolution]:
                return [ScopeResolution.model_validate(x) for x in p[("EXPECTED", "C04")]]

        class Temporal:
            def resolve(self, *args) -> list[ApplicableRequirement]:
                return [ApplicableRequirement.model_validate(x) for x in p[("EXPECTED", "C05")]]

        class Retrieval:
            def retrieve(self, *args) -> list[RetrievalEvidence]:
                return [
                    RetrievalEvidence.model_validate(_rebind(x, run_id))
                    for x in p[("EXPECTED", "C06")]
                ]

        class Citations:
            def validate(self, *args) -> list[CitationValidation]:
                return [
                    CitationValidation.model_validate(_rebind(x, run_id))
                    for x in p[("EXPECTED", "C09")]
                ]

        def evaluator(request: PipelineRequest, knowledge: KnowledgeSnapshot) -> PipelineResponse:
            reference = p[("EXPECTED", "PipelineResponse")]
            payload = reference["payload"]
            return PipelineResponse.model_validate(
                {
                    **reference,
                    **request.model_dump(mode="json", exclude={"contract_name", "payload"}),
                    "payload": {
                        **payload,
                        "criterion_results": [
                            _rebind(x, run_id) for x in payload["criterion_results"]
                        ],
                    },
                }
            )

        steps = Steps()
        modules = DraftModules(
            intake=steps,
            documents=steps,
            scope=Scope(),
            temporal=Temporal(),
            retrieval=Retrieval(),
            citations=Citations(),
            observations=steps,
        )
        return modules, evaluator
