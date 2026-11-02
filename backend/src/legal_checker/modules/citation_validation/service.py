"""Step 3B / BR-20–24: never decides the applicable-law checklist."""

from collections.abc import Mapping
from datetime import date
from typing import Protocol

from legal_checker.modules.citation_validation.classifier import classify
from legal_checker.modules.citation_validation.domain_validator import (
    DEFAULT_DOMAIN_PREFIXES,
    validate_domain,
)
from legal_checker.modules.citation_validation.identity_validator import validate_identity
from legal_checker.modules.citation_validation.temporal_validator import validate_temporal
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.citation import CitationExtraction, CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import ContractProfile
from legal_checker.shared.ids import citation_finding_id


class CitationValidator(Protocol):
    def validate(
        self,
        context: Context,
        profile: ContractProfile,
        citations: list[CitationExtraction],
        knowledge: KnowledgeSnapshot,
    ) -> list[CitationValidation]: ...


def relevant_date(profile: ContractProfile) -> date | None:
    """Signing date: the SIGNING marker when it has a date, else the profile field."""
    signing = [m.ngay for m in profile.time_markers if m.loai_moc == "SIGNING" and m.ngay]
    return signing[0] if len(set(signing)) == 1 else profile.profile.ngay_giao_ket


class CatalogCitationValidator:
    """Classify each contract-authored citation occurrence against the legal catalog.

    One C09 finding per C03 occurrence. `finding_verified` is true only when the catalog
    has verified identity, temporal and domain metadata for a number-matched document;
    downstream risk rules treat unverified findings as review items.
    """

    def __init__(self, domain_prefixes: Mapping[str, tuple[str, ...]] | None = None):
        self.domain_prefixes = domain_prefixes or DEFAULT_DOMAIN_PREFIXES

    def validate(
        self,
        context: Context,
        profile: ContractProfile,
        citations: list[CitationExtraction],
        knowledge: KnowledgeSnapshot,
    ) -> list[CitationValidation]:
        foreign = [c.vien_dan_id for c in citations if c.hop_dong_id != profile.hop_dong_id]
        if foreign:
            raise ValueError(f"Citations of another contract: {foreign[:3]}")
        relations = knowledge.tables["quan_he_van_ban"]
        contract_types = {r["loai_hop_dong_id"]: r for r in knowledge.tables["loai_hop_dong"]}
        day = relevant_date(profile)
        findings = []
        for citation in citations:
            identity = validate_identity(citation, knowledge.documents)
            document = identity.document
            temporal = validate_temporal(document, relations, day) if document else None
            domain_status, domain_detail = (
                validate_domain(document, profile, contract_types, self.domain_prefixes)
                if document
                else ("UNKNOWN", "no identified document")
            )
            result = classify(identity, temporal, domain_status)
            verified = bool(
                document
                and identity.status == "MATCHED"
                and citation.extraction.status == "EXTRACTED"
                and all(
                    document.get(flag) is True
                    for flag in ("identity_verified", "temporal_verified", "domain_verified")
                )
            )
            normalized = citation.normalized
            findings.append(
                CitationValidation(
                    finding_id=citation_finding_id(
                        context.ca_id, profile.hop_dong_id, citation.vien_dan_id
                    ),
                    ca_id=context.ca_id,
                    vien_dan_id=citation.vien_dan_id,
                    normalized_van_ban_id=document["van_ban_id"] if document else None,
                    relevant_date=day,
                    status=result.status,
                    reason_code=result.reason_code,
                    ly_do=result.ly_do,
                    domain_status=domain_status,
                    finding_verified=verified,
                    current_status=document.get("trang_thai") if document else None,
                    replacement_van_ban_id=(
                        (temporal and temporal.replacement_van_ban_id)
                        or (document.get("van_ban_thay_the_id") if document else None)
                    ),
                    source_snapshot_json={
                        "catalog_number_matched": identity.status != "UNKNOWN"
                        or identity.reason_code == "MULTIPLE_CATALOG_CANDIDATES",
                        "evidence_ids": [e.doan_id for e in citation.evidence],
                        "legal_gold": False,
                        "reviewed_knowledge": verified,
                        "source_occurrence": {
                            "vien_dan_id": citation.vien_dan_id,
                            "observed_number": normalized.so_hieu,
                            "observed_title": normalized.ten_van_ban,
                            "dieu": normalized.dieu,
                            "khoan": normalized.khoan,
                            "extraction_status": citation.extraction.status,
                        },
                        "checks": {
                            "identity": {
                                "status": identity.status,
                                "reason_code": identity.reason_code,
                                "candidates": identity.candidates,
                                "detail": identity.detail,
                            },
                            "temporal": (
                                {
                                    "status": temporal.status,
                                    "reason_code": temporal.reason_code,
                                    "detail": temporal.detail,
                                }
                                if temporal
                                else None
                            ),
                            "domain": {"status": domain_status, "detail": domain_detail},
                        },
                    },
                    lan_chay_id=context.run_id,
                    knowledge_version=context.legal_knowledge_version,
                )
            )
        return findings
