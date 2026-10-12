from typing import Protocol

from app.contracts.pipeline import PipelineRequest, PipelineResponse


class AssessmentStore(Protocol):
    """Persist/retrieve immutable assessment runs; adapters own transaction details."""

    def get(self, ca_id: str, run_id: str) -> PipelineResponse | None: ...
    def save(self, request: PipelineRequest, response: PipelineResponse) -> PipelineResponse: ...
