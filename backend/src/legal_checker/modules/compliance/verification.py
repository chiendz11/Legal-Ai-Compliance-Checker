"""Independent backend facts before analysis, separate from review of an AI proposal.

Load these records from a trusted backend/reviewer. They attest checks already
performed; creating a DTO does not perform those checks or authenticate a reviewer.
There is deliberately no predicate_verified or proposal digest here.
"""

from decimal import Decimal
from typing import Literal, Protocol

from pydantic import ConfigDict, Field

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.common import Context, Model
from legal_checker.shared.contracts.document_intelligence import (
    Chunk,
    ContractProfile,
    DocumentReadCoverage,
)
from legal_checker.shared.contracts.reasoning import ExternalEvidenceRegistration, Gates
from legal_checker.shared.contracts.temporal import ApplicableRequirement


class VerifiedExternalExcerpt(Model):
    """Text extracted and checked by the backend against a registered source file."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    bang_chung_id: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    text: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)


class CriterionVerification(Context):
    """Context-bound pre-analysis attestation; it cannot approve an AI's conclusion."""

    hop_dong_id: str
    yeu_cau_ca_id: str
    tieu_chi_id: str
    verification_reference: str = Field(min_length=1)
    gates: Gates = Field(default_factory=Gates)
    local_applicability: Literal["MATCH", "NO_MATCH", "UNKNOWN"] = "UNKNOWN"
    mandatory_confirmed: bool = False
    all_pages_readable: bool = False
    all_related_documents_received: bool = False
    template_field_unfilled: bool = False
    facts: dict[str, Decimal | bool | str | None] = Field(default_factory=dict)
    facts_verified: bool = False
    external_excerpts: list[VerifiedExternalExcerpt] = Field(default_factory=list)


class CriterionVerificationProvider(Protocol):
    """Person 4 supplies checks; person 5 injects it before C07 for this exact run.

    No default provider invents human review or promotes AI candidate facts.
    An empty result explicitly leaves criteria requiring attestations UNKNOWN.
    """

    def verify(
        self,
        context: Context,
        profile: ContractProfile,
        requirements: list[ApplicableRequirement],
        chunks: list[Chunk],
        knowledge: KnowledgeSnapshot,
        *,
        coverage: DocumentReadCoverage | None = None,
    ) -> list[CriterionVerification]: ...


class EvidenceRegistryProvider(Protocol):
    """Trusted source registration, separately supplied before criterion verification.

    Person 2 supplies source bytes/locators; person 4 attests checks and person 5 injects.
    A provider must check bytes/hash before setting verified, not just build this DTO.
    """

    def load(
        self, context: Context, case: AssessmentCase, knowledge: KnowledgeSnapshot
    ) -> list[ExternalEvidenceRegistration]: ...
