"""Fixture-only upstream services for integration tests; each slot can be replaced."""

from types import SimpleNamespace

from app.contracts.handoffs import HandoffSet
from app.workflows.pipelines.draft_assessment import DraftModules


def fixture_modules(handoffs: HandoffSet) -> DraftModules:
    """Fresh copies ensure one run cannot mutate another owner's fixture input."""
    h = handoffs
    return DraftModules(
        intake=SimpleNamespace(register=lambda case: case),
        documents=SimpleNamespace(extract=lambda case: h.document_output.model_copy(deep=True)),
        scope=SimpleNamespace(
            resolve=lambda context, profile, knowledge: [
                item.model_copy(deep=True) for item in h.legal_output.scope
            ]
        ),
        temporal=SimpleNamespace(
            resolve=lambda context, profile, scope, knowledge: [
                item.model_copy(deep=True) for item in h.legal_output.requirements
            ]
        ),
        citations=SimpleNamespace(
            validate=lambda context, profile, citations, knowledge: [
                item.model_copy(deep=True) for item in h.legal_output.citations
            ]
        ),
        retrieval=SimpleNamespace(
            retrieve=lambda context, requirements, chunks, knowledge: [
                item.model_copy(deep=True) for item in h.retrieval_output
            ]
        ),
        observations=SimpleNamespace(
            observe=lambda context, profile, requirements, retrieval, chunks, knowledge: [
                item.model_copy(deep=True) for item in h.compliance_input.payload.observations
            ]
        ),
    )
