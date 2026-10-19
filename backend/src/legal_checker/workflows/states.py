"""Persisted full-assessment run states and the stage names reported to the UI.

Run status is processing state only; it is never a legal label. COMPLETED means machine
outputs exist, not that anything was reviewed or published.
"""

from collections.abc import Callable
from typing import Literal

RunStatus = Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"]
StageStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"]
Stage = Literal[
    "INTAKE",
    "DOCUMENT_INTELLIGENCE",
    "SCOPE_RESOLUTION",
    "TEMPORAL_RESOLUTION",
    "CITATION_VALIDATION",
    "RETRIEVAL",
    "COMPLIANCE",
    "RISK_AGGREGATION",
    "RECOMMENDATION",
]

STAGES: tuple[Stage, ...] = (
    "INTAKE",
    "DOCUMENT_INTELLIGENCE",
    "SCOPE_RESOLUTION",
    "TEMPORAL_RESOLUTION",
    "CITATION_VALIDATION",
    "RETRIEVAL",
    "COMPLIANCE",
    "RISK_AGGREGATION",
    "RECOMMENDATION",
)

# A progress sink called by the workflow; the runner persists each transition.
StageCallback = Callable[[Stage, StageStatus], None]


def initial_stages() -> list[dict]:
    return [{"stage": stage, "status": "PENDING"} for stage in STAGES]


def no_progress(stage: Stage, status: StageStatus) -> None:
    """Default callback for callers that do not track progress."""
