"""Wiring skeleton for steps 1–7 with explicitly injected upstream implementations.

There are no default OCR, scope, temporal, retrieval or LLM implementations.
Steps 5–7 default to the group C skeleton, which stops with NotImplementedError at step 5;
callers may inject another evaluator with the same signature.
"""

from collections.abc import Callable
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
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.handoffs import LegalOutput
from legal_checker.shared.contracts.pipeline import (
    PipelinePayload,
    PipelineRequest,
    PipelineResponse,
)
from legal_checker.shared.contracts.workflow import AssessmentDraft
from legal_checker.shared.validation import validate_context, validate_requirements
from legal_checker.workflows.handoffs import validate_document, validate_legal
from legal_checker.workflows.states import Stage, StageCallback, no_progress
from legal_checker.workflows.steps_5_7 import evaluate

Evaluator = Callable[[PipelineRequest, KnowledgeSnapshot], PipelineResponse]


@dataclass(frozen=True)
class DraftModules:
    intake: IntakeService
    documents: DocumentIntelligenceService
    scope: ScopeResolver
    temporal: TemporalResolver
    retrieval: RetrievalService
    citations: CitationValidator
    observations: ObservationProvider


class _StageTracker:
    """Reports RUNNING/COMPLETED around a stage and FAILED if it raises."""

    def __init__(self, callback: StageCallback):
        self.callback = callback

    def __call__(self, stage: Stage, action):
        self.callback(stage, "RUNNING")
        try:
            result = action()
        except Exception:
            self.callback(stage, "FAILED")
            raise
        self.callback(stage, "COMPLETED")
        return result


class DraftAssessmentWorkflow:
    def __init__(
        self,
        modules: DraftModules,
        knowledge: KnowledgeSnapshot,
        *,
        evaluator: Evaluator | None = None,
    ):
        self.modules = modules
        self.knowledge = knowledge
        self.evaluator = evaluator or evaluate

    def evaluate(
        self, case: AssessmentCase, context: Context, on_stage: StageCallback = no_progress
    ) -> AssessmentDraft:
        validate_context(context, self.knowledge)
        if case.ca_id != context.ca_id:
            raise ValueError("Assessment case differs from workflow context")
        for key, value in case.deployment.model_dump().items():
            if getattr(context, key) != value:
                raise ValueError("Assessment deployment differs from workflow context")
        stage = _StageTracker(on_stage)

        def intake():
            registered = self.modules.intake.register(case.model_copy(deep=True))
            if registered != case:
                raise ValueError("Intake changed the pinned assessment case")
            return registered

        registered = stage("INTAKE", intake)

        def extract():
            document = self.modules.documents.extract(registered.model_copy(deep=True))
            validate_document(registered, document)
            return document

        document = stage("DOCUMENT_INTELLIGENCE", extract)

        # Branch A receives profile/knowledge, never contract-authored citations.
        def resolve_scope():
            scope = self.modules.scope.resolve(context, document.contract_profile, self.knowledge)
            if len({item.yeu_cau_ca_id for item in scope}) != len(scope) or any(
                item.ca_id != context.ca_id for item in scope
            ):
                raise ValueError("Scope checklist contains duplicate IDs or a foreign case")
            return scope

        scope = stage("SCOPE_RESOLUTION", resolve_scope)
        scope_by_id = {item.yeu_cau_ca_id: item for item in scope}

        def resolve_temporal():
            requirements = self.modules.temporal.resolve(
                context,
                document.contract_profile,
                [item.model_copy(deep=True) for item in scope],
                self.knowledge,
            )
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
            return requirements

        requirements = stage("TEMPORAL_RESOLUTION", resolve_temporal)

        # Branch B independently validates citations and joins A only at Risk/Report.
        def validate_citations():
            citations = self.modules.citations.validate(
                context, document.contract_profile, document.citations, self.knowledge
            )
            validate_legal(
                context,
                document,
                LegalOutput(scope=scope, requirements=requirements, citations=citations),
                self.knowledge,
            )
            return citations

        citations = stage("CITATION_VALIDATION", validate_citations)
        retrieval = stage(
            "RETRIEVAL",
            lambda: self.modules.retrieval.retrieve(
                context, requirements, document.chunks, self.knowledge
            ),
        )

        def assess():
            observations = self.modules.observations.observe(
                context,
                document.contract_profile,
                requirements,
                retrieval,
                document.chunks,
                self.knowledge,
            )
            return self.evaluator(
                PipelineRequest(
                    **context.model_dump(),
                    payload=PipelinePayload(
                        hop_dong_id=case.hop_dong_id,
                        requirements=requirements,
                        chunks=document.chunks,
                        retrieval=retrieval,
                        observations=observations,
                        citations=citations,
                    ),
                ),
                self.knowledge,
            )

        # Steps 5–7 run as one group C call, so its three stages share one outcome.
        on_stage("COMPLIANCE", "RUNNING")
        try:
            evaluation = assess()
        except Exception:
            for name in ("COMPLIANCE", "RISK_AGGREGATION", "RECOMMENDATION"):
                on_stage(name, "FAILED")
            raise
        for name in ("COMPLIANCE", "RISK_AGGREGATION", "RECOMMENDATION"):
            on_stage(name, "COMPLETED")
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
