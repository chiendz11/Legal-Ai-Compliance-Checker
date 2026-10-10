from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Finding = Literal["SATISFIED", "MISSING", "VIOLATED", "UNKNOWN"]
RequirementStatus = Literal["COMPLIANT", "PARTIAL", "NON_COMPLIANT", "INSUFFICIENT"]
RiskType = Literal["COMPLIANCE", "CITATION", "VERIFICATION"]
Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "REVIEW_REQUIRED"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Context(Model):
    contract_version: Literal["1.0"] = "1.0"
    ca_id: str = Field(min_length=1)
    phien_ban_id: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    legal_knowledge_version: str = Field(min_length=1)
    knowledge_snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    run_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)


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


class ApplicableRequirement(Model):
    yeu_cau_ca_id: str = Field(min_length=1)
    ca_id: str = Field(min_length=1)
    requirement_id: str = Field(min_length=1)
    requirement_version_id: str | None = None
    nhom_phien_ban: str | None = None
    scope_status: Literal["MATCH", "NO_MATCH", "UNKNOWN"]
    version_status: Literal["RESOLVED", "UNKNOWN"]
    applicability_status: Literal["CONFIRMED", "NOT_APPLICABLE", "UNKNOWN"]
    moc_id: str | None = None
    loai_moc: str | None = None
    moc_ap_dung: date | None = None
    resolution_method: str | None = None
    profile_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    dieu_kien_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    nguon_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    phien_ban_id: str
    reason: dict[str, str] = Field(default_factory=dict)

    @property
    def confirmed(self) -> bool:
        return (
            self.scope_status == "MATCH"
            and self.version_status == "RESOLVED"
            and self.applicability_status == "CONFIRMED"
        )

    @model_validator(mode="after")
    def consistent(self):
        if self.confirmed and (not self.requirement_version_id or not self.moc_ap_dung):
            raise ValueError("Confirmed requirement needs version and relevant date")
        if self.applicability_status == "CONFIRMED" and not self.confirmed:
            raise ValueError("CONFIRMED requires MATCH and RESOLVED")
        return self


class Chunk(Model):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    doan_id: str = Field(min_length=1)
    hop_dong_id: str = Field(min_length=1)
    noi_dung: str = Field(min_length=1)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)

    @model_validator(mode="after")
    def page_range(self):
        if self.page_end < self.page_start:
            raise ValueError("Invalid page range")
        return self


class Evidence(Model):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    doan_id: str
    trich_dan: str = Field(min_length=1)
    ky_tu_bat_dau: int = Field(ge=0)
    ky_tu_ket_thuc: int = Field(ge=1)

    @model_validator(mode="after")
    def offsets(self):
        if self.ky_tu_ket_thuc <= self.ky_tu_bat_dau:
            raise ValueError("Evidence offsets must define a nonempty interval")
        return self


class ExternalEvidence(Model):
    bang_chung_id: str
    object_uri: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    verified: bool = False


class RetrievalEvidence(Model):
    truy_xuat_id: str
    yeu_cau_ca_id: str
    tieu_chi_id: str
    doan_id: str
    giai_doan: str = "FINAL"
    scores: dict[str, float | None] = Field(default_factory=dict)
    thu_hang: int = Field(ge=1)
    duoc_chon: bool
    query_text: str = ""
    retrieval_version: str
    embedding_model: str | None = None
    index_version: str
    rerank_model: str | None = None
    lan_chay_id: str


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


class RequirementResult(Model):
    tuan_thu_id: str
    yeu_cau_ca_id: str
    status: RequirementStatus
    so_tieu_chi_ap_dung: int
    so_tieu_chi_da_danh_gia: int
    so_unknown: int
    rule_version: str
    giai_thich: str
    requirement_snapshot_json: dict[str, Any]
    coverage_complete: bool


class CitationValidation(Model):
    finding_id: str
    ca_id: str
    vien_dan_id: str
    normalized_van_ban_id: str | None = None
    relevant_date: date | None = None
    status: Literal["VALID", "STALE", "INVALID", "UNKNOWN"]
    reason_code: str
    ly_do: str
    domain_status: Literal["MATCH", "MISMATCH", "UNKNOWN"]
    finding_verified: bool
    current_status: str | None = None
    replacement_van_ban_id: str | None = None
    source_snapshot_json: dict[str, Any]
    lan_chay_id: str
    knowledge_version: str


class RiskSource(Model):
    yeu_cau_ca_id: str | None = None
    ket_qua_tieu_chi_id: str | None = None
    citation_finding_id: str | None = None

    @model_validator(mode="after")
    def single_source(self):
        if bool(self.ket_qua_tieu_chi_id) == bool(self.citation_finding_id):
            raise ValueError("Risk must reference exactly one criterion or citation finding")
        return self


class RiskResult(Model):
    ket_qua_rui_ro_id: str
    ca_id: str
    risk_type: RiskType
    rui_ro_id: str
    severity: Severity
    source: RiskSource
    quy_tac_id: str
    giai_thich: str
    risk_snapshot: dict[str, Any]
    rule_snapshot_json: dict[str, Any]
    evidence_ids: list[str]
    legal_basis_ids: list[str]
    review_status: Literal["PENDING"] = "PENDING"


class Recommendation(Model):
    khuyen_nghi_ca_id: str
    ket_qua_rui_ro_id: str
    khuyen_nghi_id: str
    noi_dung: str
    loai_hanh_dong: str
    uu_tien: Severity
    dieu_kien_snapshot: dict[str, Any]
    evidence_ids: list[str]
    legal_basis_ids: list[str]
    template_snapshot_json: dict[str, Any]
    rule_version: str
    knowledge_snapshot_sha256: str
    model_version: Literal["TEMPLATE_ENGINE_NO_LLM"] = "TEMPLATE_ENGINE_NO_LLM"
    prompt_version: Literal["NOT_USED"] = "NOT_USED"
    review_status: Literal["PENDING"] = "PENDING"


class PipelinePayload(Model):
    hop_dong_id: str
    requirements: list[ApplicableRequirement] = Field(min_length=1)
    chunks: list[Chunk] = Field(default_factory=list)
    retrieval: list[RetrievalEvidence] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    citations: list[CitationValidation] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_ids(self):
        for attr, key in [
            ("requirements", "yeu_cau_ca_id"),
            ("chunks", "doan_id"),
            ("observations", "tieu_chi_id"),
            ("citations", "finding_id"),
            ("retrieval", "truy_xuat_id"),
        ]:
            rows = getattr(self, attr)
            ids = [getattr(r, key) for r in rows]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate IDs in {attr}")
        return self


class PipelineRequest(Context):
    contract_name: Literal["Steps57Input"] = "Steps57Input"
    payload: PipelinePayload


class PipelineResult(Model):
    criterion_results: list[CriterionResult]
    requirement_results: list[RequirementResult]
    risks: list[RiskResult]
    recommendations: list[Recommendation]
    excluded_requirements: list[str]


class PipelineResponse(Context):
    contract_name: Literal["Steps57Result"] = "Steps57Result"
    produced_at: datetime
    payload: PipelineResult
