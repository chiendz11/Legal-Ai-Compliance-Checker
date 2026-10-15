from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, model_validator

from legal_checker.shared.contracts.common import Context, Finding, Model
from legal_checker.shared.contracts.document_intelligence import Chunk, Evidence, ExternalEvidence
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.shared.contracts.temporal import ApplicableRequirement


class Gates(Model):
    coverage_complete: bool = False
    absence_verified: bool = False
    evidence_validated: bool = False
    source_verified: bool = False
    scope_confirmed: bool = False
    version_resolved: bool = False
    evidence_conflict: bool = False
    exceptions_resolved: bool = False

    def reliable(self) -> bool:
        return all(
            [
                self.evidence_validated,
                self.source_verified,
                self.scope_confirmed,
                self.version_resolved,
                self.exceptions_resolved,
                not self.evidence_conflict,
            ]
        )

    def missing_allowed(self) -> bool:
        return self.reliable() and self.coverage_complete and self.absence_verified


class Observation(Model):
    """Structured assertion from a rule/LLM adapter; this is never trusted without gates."""

    tieu_chi_id: str
    proposed_finding: Finding = "UNKNOWN"
    giai_thich: str = Field(min_length=1)
    gates: Gates = Field(default_factory=Gates)
    evidence: list[Evidence] = Field(default_factory=list)
    external_evidence: list[ExternalEvidence] = Field(default_factory=list)
    local_applicability: Literal["MATCH", "NO_MATCH", "UNKNOWN"] = "UNKNOWN"
    exclusion_reason: str | None = None
    mandatory_confirmed: bool = False
    all_pages_readable: bool = False
    all_related_documents_received: bool = False
    template_field_unfilled: bool = False
    facts: dict[str, Decimal | bool | str | None] = Field(default_factory=dict)
    facts_verified: bool = False
    model_version: str = "STRUCTURED_ADAPTER_NO_LLM"
    prompt_version: str = "NOT_USED"


class CriterionResult(Model):
    ket_qua_id: str
    ca_id: str
    yeu_cau_ca_id: str
    tieu_chi_id: str
    finding: Finding
    giai_thich: str
    gates: Gates
    uncertainty_reason: str | None = None
    pham_vi_ket_luan: Literal["CURRENT_CRITERION"] = "CURRENT_CRITERION"
    evidence: list[Evidence] = Field(default_factory=list)
    external_evidence: list[ExternalEvidence] = Field(default_factory=list)
    legal_basis_ids: list[str] = Field(default_factory=list)
    tieu_chi_snapshot_json: dict[str, Any]
    model_version: str
    prompt_version: str
    lan_chay_id: str
    review_status: Literal["PENDING"] = "PENDING"
    mandatory: bool
    excluded: bool = False
    exclusion_reason: str | None = None

    @model_validator(mode="after")
    def validate_finding(self):
        if self.finding == "MISSING" and not self.gates.missing_allowed():
            raise ValueError("MISSING requires all absence and reliability gates")
        if self.finding in ("SATISFIED", "VIOLATED"):
            if not self.gates.reliable() or not (self.evidence or self.external_evidence):
                raise ValueError("Content findings require reliable, attributable evidence")
        if self.finding != "UNKNOWN" and not self.legal_basis_ids:
            raise ValueError("Known findings require legal provenance")
        if self.finding != "UNKNOWN" and any(not e.verified for e in self.external_evidence):
            raise ValueError("External evidence is unverified")
        if self.finding == "UNKNOWN" and not self.uncertainty_reason:
            raise ValueError("UNKNOWN needs uncertainty_reason")
        if self.excluded and not self.exclusion_reason:
            raise ValueError("Excluded criterion needs reason")
        return self


class ReasoningPayload(Model):
    """C05 + C06 + evidence/observations. Citation validation is a separate branch."""

    hop_dong_id: str
    requirements: list[ApplicableRequirement] = Field(min_length=1)
    chunks: list[Chunk] = Field(default_factory=list)
    retrieval: list[RetrievalEvidence] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_ids(self):
        for attr, key in [
            ("requirements", "yeu_cau_ca_id"),
            ("chunks", "doan_id"),
            ("observations", "tieu_chi_id"),
            ("retrieval", "truy_xuat_id"),
        ]:
            ids = [getattr(row, key) for row in getattr(self, attr)]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate IDs in {attr}")
        return self


class ReasoningRequest(Context):
    contract_name: Literal["CriterionReasoningInput"] = "CriterionReasoningInput"
    payload: ReasoningPayload
