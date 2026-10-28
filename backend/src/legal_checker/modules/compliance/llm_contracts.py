"""Untrusted semantic output; no field here can approve a verification gate."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from legal_checker.shared.contracts.common import Finding, Model
from legal_checker.shared.contracts.reasoning import Observation


class ProposedQuote(BaseModel):
    """Keep original characters; backend resolves/validates the optional start offset."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=False)
    doan_id: str
    trich_dan: str
    ky_tu_bat_dau: int | None


class CandidateFact(BaseModel):
    """An extraction candidate, never a verified numeric or applicability fact."""

    model_config = ConfigDict(extra="forbid", strict=True)
    name: str
    value: str | None
    unit: str | None
    evidence_ids: list[str]


class SemanticProposal(BaseModel):
    """Required fields also form the strict Responses API JSON schema."""

    model_config = ConfigDict(extra="forbid", strict=True)
    tieu_chi_id: str
    proposed_finding: Finding
    giai_thich: str
    checked_conditions: list[str]
    missing_conditions: list[str]
    verification_requirements: list[str]
    evidence: list[ProposedQuote]
    external_evidence_ids: list[str]
    candidate_facts: list[CandidateFact]


class CriterionAnalysis(Model):
    """Traceable proposal and its checked Observation, kept separate for review/replay."""

    tieu_chi_id: str
    input_sha256: str
    origin: Literal["OPENAI", "REPLAY", "NO_CALL"]
    model_version: str
    prompt_version: str
    proposal: SemanticProposal | None = None
    observation_proposal: Observation | None = None
    observation: Observation
    error_code: str | None = None
    request_id: str | None = None


class ObservationBatch(Model):
    """Exactly one record/Observation per criterion with a known checklist version."""

    observations: list[Observation]
    analyses: list[CriterionAnalysis]
