"""Load checked fixtures, run reference stages and validate an owner's real output."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from legal_checker.core.config import PROJECT_ROOT
from legal_checker.modules.compliance.service import evaluate_compliance
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.reports.builder import build_draft_report
from legal_checker.shared.contracts.assessment import SourceDocument
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import DocumentIntelligenceResult
from legal_checker.shared.contracts.handoffs import (
    ComplianceOutput,
    FixtureManifest,
    HandoffSet,
    LegalOutput,
)
from legal_checker.shared.contracts.pipeline import PipelineRequest
from legal_checker.shared.contracts.report import FinalReport
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.workflows.assessment_workflow import DraftAssessmentWorkflow
from legal_checker.workflows.handoffs import (
    report_input_from_draft,
    validate_case,
    validate_compliance,
    validate_document,
    validate_legal,
    validate_report,
    validate_retrieval,
)
from legal_checker.workflows.steps_5_7 import evaluate
from pydantic import BaseModel, TypeAdapter

from devtools.replay import fixture_modules

FIXTURE_ROOT = PROJECT_ROOT / "examples/parallel"
SCENARIOS = (
    "satisfied",
    "violated",
    "missing",
    "partial",
    "insufficient_evidence",
    "unknown_version",
    "stale_citation",
)
OUTPUT_TYPES = {
    1: DocumentIntelligenceResult,
    2: LegalOutput,
    3: list[RetrievalEvidence],
    4: ComplianceOutput,
    5: FinalReport,
}


def json_text(value) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [v.model_dump(mode="json") if isinstance(v, BaseModel) else v for v in value]
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def pipeline_request(handoffs: HandoffSet) -> PipelineRequest:
    reasoning = handoffs.compliance_input
    return PipelineRequest(
        **reasoning.model_dump(exclude={"contract_name", "payload"}),
        payload={
            **reasoning.payload.model_dump(),
            "citations": [item.model_dump() for item in handoffs.legal_output.citations],
        },
    )


def validate_handoffs(h: HandoffSet, knowledge: KnowledgeSnapshot):
    context = h.document_input.context
    case = h.document_input.case
    validate_case(context, case, knowledge)
    validate_document(case, h.document_output)
    profile = h.document_output.contract_profile
    for request in (h.scope_input, h.temporal_input, h.citation_input):
        if request.context != context or request.contract_profile != profile:
            raise ValueError("Legal input changed the document/context handoff")
    if (
        h.citation_input.citations != h.document_output.citations
        or h.citation_input.chunks != h.document_output.chunks
    ):
        raise ValueError("Citation input differs from document extraction")
    if h.temporal_input.scope != h.legal_output.scope:
        raise ValueError("Temporal input differs from scope output")
    validate_legal(context, h.document_output, h.legal_output, knowledge)
    if (
        h.retrieval_input.context != context
        or h.retrieval_input.hop_dong_id != case.hop_dong_id
        or h.retrieval_input.requirements != h.legal_output.requirements
        or h.retrieval_input.chunks != h.document_output.chunks
    ):
        raise ValueError("Retrieval input changed a predecessor handoff")
    validate_retrieval(h.retrieval_input, h.retrieval_output, knowledge)
    reasoning_context = Context(
        **h.compliance_input.model_dump(exclude={"contract_name", "payload"})
    )
    payload = h.compliance_input.payload
    if (
        reasoning_context != context
        or payload.hop_dong_id != case.hop_dong_id
        or payload.requirements != h.legal_output.requirements
        or payload.chunks != h.document_output.chunks
        or payload.retrieval != h.retrieval_output
    ):
        raise ValueError("Reasoning input changed a predecessor handoff")
    validate_compliance(h.compliance_input, h.compliance_output, knowledge)
    integration = h.integration_input
    if (
        integration.context != context
        or integration.case != case
        or integration.document != h.document_output
        or integration.legal != h.legal_output
        or integration.compliance != h.compliance_output
    ):
        raise ValueError("Integration input changed a predecessor handoff")
    actual = evaluate(pipeline_request(h), knowledge)
    actual.produced_at = h.pipeline_output.produced_at
    if actual != h.pipeline_output:
        raise ValueError("Pipeline checkpoint differs from the reference engines")
    if build_draft_report(integration, knowledge) != h.report_output:
        raise ValueError("Report checkpoint differs from the pinned draft builder")
    validate_report(integration, h.report_output, knowledge)


@dataclass(frozen=True)
class FixturePack:
    directory: Path
    manifest: FixtureManifest
    handoffs: HandoffSet

    def read_source(self, source: SourceDocument) -> bytes:
        """Fixture-only SourceStorage capability for the document owner's parser tests."""
        if source != self.handoffs.document_input.case.source:
            raise ValueError("SourceStorage received a foreign fixture source")
        content = (self.directory / "source.docx").read_bytes()
        if hashlib.sha256(content).hexdigest() != source.sha256:
            raise ValueError("Source document checksum changed")
        return content

    @classmethod
    def load(cls, directory: Path, knowledge: KnowledgeSnapshot):
        manifest = FixtureManifest.model_validate_json((directory / "manifest.json").read_text())
        if manifest.knowledge_snapshot_sha256 != knowledge.sha256:
            raise ValueError("Fixture knowledge checksum differs from the selected snapshot")
        expected_files = {f"{name}.json" for name in HandoffSet.model_fields} | {"source.docx"}
        if set(manifest.files) != expected_files:
            raise ValueError("Manifest must list exactly the handoff files and source.docx")
        for name, digest in manifest.files.items():
            if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Fixture file checksum mismatch: {name}")
        handoffs = HandoffSet.model_validate(
            {
                name: json.loads((directory / f"{name}.json").read_text())
                for name in HandoffSet.model_fields
            }
        )
        if handoffs.document_input.case.source.sha256 != manifest.files["source.docx"]:
            raise ValueError("C01 source hash differs from the fixture document")
        if (
            handoffs.document_input.case.source.object_uri
            != f"fixture://parallel/{manifest.scenario}/source.docx"
        ):
            raise ValueError("Fixture source URI does not match its manifest")
        validate_handoffs(handoffs, knowledge)
        output = handoffs.pipeline_output.payload
        counts = {
            kind: sum(r.risk_type == kind for r in output.risks)
            for kind in ("COMPLIANCE", "CITATION", "VERIFICATION")
        }
        expected = manifest.expected
        if (
            [r.finding for r in output.criterion_results] != expected.criterion_findings
            or [r.status for r in output.requirement_results] != [expected.requirement_status]
            or counts
            != {
                "COMPLIANCE": expected.compliance_risks,
                "CITATION": expected.citation_risks,
                "VERIFICATION": expected.verification_risks,
            }
        ):
            raise ValueError("Fixture results differ from scenario expectations")
        return cls(directory, manifest, handoffs)

    def input_for(self, person: int):
        h = self.handoffs
        return {
            1: h.document_input.model_dump(mode="json"),
            2: {
                name: getattr(h, name).model_dump(mode="json")
                for name in ("scope_input", "temporal_input", "citation_input")
            },
            3: h.retrieval_input.model_dump(mode="json"),
            4: h.compliance_input.model_dump(mode="json"),
            5: h.integration_input.model_dump(mode="json"),
        }[person]

    def reference_output(self, person: int, knowledge: KnowledgeSnapshot):
        h = self.handoffs
        if person == 1:
            return h.document_output.model_copy(deep=True)
        if person == 2:
            return h.legal_output.model_copy(deep=True)
        if person == 3:
            return [item.model_copy(deep=True) for item in h.retrieval_output]
        if person == 4:
            return evaluate_compliance(h.compliance_input, knowledge).model_copy(deep=True)
        draft = DraftAssessmentWorkflow(fixture_modules(h), knowledge).evaluate(
            h.document_input.case, h.document_input.context
        )
        return build_draft_report(report_input_from_draft(draft), knowledge).model_copy(deep=True)

    def validate_output(self, person: int, data, knowledge: KnowledgeSnapshot):
        output = TypeAdapter(OUTPUT_TYPES[person]).validate_python(data)
        h = self.handoffs
        if person == 1:
            validate_document(h.document_input.case, output)
        elif person == 2:
            validate_legal(h.document_input.context, h.document_output, output, knowledge)
        elif person == 3:
            validate_retrieval(h.retrieval_input, output, knowledge)
        elif person == 4:
            validate_compliance(h.compliance_input, output, knowledge)
        else:
            validate_report(h.integration_input, output, knowledge)
        return output
