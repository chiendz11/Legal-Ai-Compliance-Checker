"""Draft workflow for steps 1–7 with explicitly injected upstream implementations.

There are no default OCR, scope, temporal, retrieval or LLM implementations.
Steps 5–7 compute draft results; publication/review remain separate responsibilities.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from legal_checker.modules.applicable_law.scope_resolver import ScopeResolver
from legal_checker.modules.applicable_law.temporal_resolver import TemporalResolver
from legal_checker.modules.citation_validation.service import CitationValidator
from legal_checker.modules.compliance.observations import ObservationProvider
from legal_checker.modules.documents.intake import IntakeService
from legal_checker.modules.documents.service import DocumentIntelligenceService
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.retrieval.service import RetrievalService
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import DocumentIntelligenceResult
from legal_checker.shared.contracts.handoffs import LegalOutput, RetrievalInput
from legal_checker.shared.contracts.pipeline import PipelinePayload, PipelineRequest
from legal_checker.shared.contracts.reasoning import ExternalEvidenceRegistration, Observation
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.shared.contracts.temporal import ApplicableRequirement
from legal_checker.shared.contracts.workflow import AssessmentDraft
from legal_checker.shared.validation import validate_context, validate_requirements
from legal_checker.workflows.handoffs import validate_document, validate_legal, validate_retrieval
from legal_checker.workflows.steps_5_7 import evaluate


@dataclass(frozen=True)
class DraftModules:
    intake: IntakeService
    documents: DocumentIntelligenceService
    scope: ScopeResolver
    temporal: TemporalResolver
    retrieval: RetrievalService | None
    citations: CitationValidator | None
    observations: ObservationProvider | None
    external_evidence_registry: Sequence[ExternalEvidenceRegistration] = ()


class DraftAssessmentWorkflow:
    def __init__(self, modules: DraftModules, knowledge: KnowledgeSnapshot):
        self.modules = modules
        self.knowledge = knowledge

    def evaluate(self, case: AssessmentCase, context: Context) -> AssessmentDraft:
        validate_context(context, self.knowledge)
        if case.ca_id != context.ca_id:
            raise ValueError("Assessment case differs from workflow context")
        for key, value in case.deployment.model_dump().items():
            if getattr(context, key) != value:
                raise ValueError("Assessment deployment differs from workflow context")

        registered = AssessmentCase.model_validate(
            self.modules.intake.register(case.model_copy(deep=True)).model_dump()
        )
        if registered != case:
            raise ValueError("Intake changed the pinned assessment case")
        document = DocumentIntelligenceResult.model_validate(
            self.modules.documents.extract(registered.model_copy(deep=True)).model_dump()
        )
        validate_document(registered, document)

        # Branch A receives profile/knowledge, never contract-authored citations.
        scope = [
            ScopeResolution.model_validate(item.model_dump())
            for item in self.modules.scope.resolve(
                context.model_copy(deep=True),
                document.contract_profile.model_copy(deep=True),
                self.knowledge,
            )
        ]
        scope_by_id = {item.yeu_cau_ca_id: item for item in scope}
        if len(scope_by_id) != len(scope) or any(item.ca_id != context.ca_id for item in scope):
            raise ValueError("Scope checklist contains duplicate IDs or a foreign case")
        requirements = [
            ApplicableRequirement.model_validate(item.model_dump())
            for item in self.modules.temporal.resolve(
                context.model_copy(deep=True),
                document.contract_profile.model_copy(deep=True),
                [item.model_copy(deep=True) for item in scope],
                self.knowledge,
            )
        ]
        validate_requirements(context, requirements, self.knowledge)
        if not requirements:
            raise ValueError("An explicit checklist is required before assessment")
        if set(scope_by_id) != {item.yeu_cau_ca_id for item in requirements}:
            raise ValueError("Temporal resolution changed the scope checklist")
        for item in requirements:
            candidate = scope_by_id[item.yeu_cau_ca_id]
            if (item.requirement_id, item.scope_status) != (
                candidate.requirement_id,
                candidate.scope_status,
            ):
                raise ValueError("Temporal resolution changed scope-owned fields")
        diagnostics = []
        retrieval = []
        if self.modules.retrieval is None:
            diagnostics.append({"module": "C06", "code": "RETRIEVAL_NOT_RUN"})
        else:
            retrieval = [
                RetrievalEvidence.model_validate(item.model_dump())
                for item in self.modules.retrieval.retrieve(
                    context.model_copy(deep=True),
                    [item.model_copy(deep=True) for item in requirements],
                    [item.model_copy(deep=True) for item in document.chunks],
                    self.knowledge,
                )
            ]
        validate_retrieval(
            RetrievalInput(
                context=context,
                hop_dong_id=case.hop_dong_id,
                requirements=requirements,
                chunks=document.chunks,
            ),
            retrieval,
            self.knowledge,
        )
        observations = []
        if self.modules.observations is None:
            diagnostics.append({"module": "C07", "code": "OBSERVATION_PROVIDER_NOT_RUN"})
        else:
            observations = [
                Observation.model_validate(item.model_dump())
                for item in self.modules.observations.observe(
                    context.model_copy(deep=True),
                    document.contract_profile.model_copy(deep=True),
                    [item.model_copy(deep=True) for item in requirements],
                    [item.model_copy(deep=True) for item in retrieval],
                    [item.model_copy(deep=True) for item in document.chunks],
                    self.knowledge,
                )
            ]

        # Branch B independently validates citations and joins A only at Risk/Report.
        citations = []
        citation_status = "NOT_RUN" if self.modules.citations is None else "COMPLETED"
        if self.modules.citations is not None:
            citations = [
                CitationValidation.model_validate(item.model_dump())
                for item in self.modules.citations.validate(
                    context.model_copy(deep=True),
                    document.contract_profile.model_copy(deep=True),
                    [item.model_copy(deep=True) for item in document.citations],
                    self.knowledge,
                )
            ]
        validate_legal(
            context,
            document,
            LegalOutput(scope=scope, requirements=requirements, citations=citations),
            self.knowledge,
            citation_branch_status=citation_status,
        )
        evaluation = evaluate(
            PipelineRequest(
                **context.model_dump(),
                payload=PipelinePayload(
                    hop_dong_id=case.hop_dong_id,
                    requirements=requirements,
                    chunks=document.chunks,
                    retrieval=retrieval,
                    observations=observations,
                    external_evidence_registry=[
                        ExternalEvidenceRegistration.model_validate(item.model_dump())
                        for item in self.modules.external_evidence_registry
                    ],
                    citations=citations,
                    citation_branch_status=citation_status,
                ),
            ),
            self.knowledge,
        )
        evaluation.payload.diagnostics.extend(diagnostics)
        return AssessmentDraft(
            context=context,
            case=registered,
            contract_profile=document.contract_profile,
            chunks=document.chunks,
            extracted_citations=document.citations,
            citation_findings=citations,
            scope=scope,
            requirements=requirements,
            retrieval=retrieval,
            evaluation=evaluation,
        )
