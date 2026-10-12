"""Reproducible synthetic handoffs anchored to the existing knowledge snapshot."""

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from app.business_modules.compliance_reasoning.runner import evaluate_compliance
from app.business_modules.reporting.draft import build_draft_report
from app.contracts.assessment import AssessmentCase
from app.contracts.citation import CitationExtraction, CitationValidation
from app.contracts.common import Context
from app.contracts.document_intelligence import ContractProfile, DocumentIntelligenceResult
from app.contracts.handoffs import (
    CitationInput,
    DocumentInput,
    FixtureManifest,
    HandoffSet,
    IntegrationInput,
    LegalOutput,
    RetrievalInput,
    ScopeInput,
    TemporalInput,
)
from app.contracts.pipeline import PipelineRequest
from app.contracts.reasoning import ReasoningPayload, ReasoningRequest
from app.contracts.scope import ScopeResolution
from app.contracts.temporal import ApplicableRequirement
from app.workflows.interfaces.knowledge import KnowledgeSnapshot
from app.workflows.pipelines.steps_5_7 import evaluate
from devtools.parallel import SCENARIOS, json_text, validate_handoffs

NOTICE = "SYNTHETIC_NOT_GOLD_NOT_HUMAN_VERIFIED"
EXPECTED = {
    "satisfied": ("COMPLIANT", ["SATISFIED"] * 3, 0, 0, 0),
    "violated": ("NON_COMPLIANT", ["VIOLATED", "SATISFIED", "SATISFIED"], 1, 0, 0),
    "missing": ("NON_COMPLIANT", ["MISSING"] * 3, 3, 0, 0),
    "partial": ("PARTIAL", ["SATISFIED", "MISSING", "MISSING"], 2, 0, 0),
    "insufficient_evidence": ("INSUFFICIENT", ["UNKNOWN"] * 3, 0, 0, 3),
    "unknown_version": ("INSUFFICIENT", [], 0, 0, 0),
    "stale_citation": ("COMPLIANT", ["SATISFIED"] * 3, 0, 1, 0),
}


def docx_bytes(text: str) -> bytes:
    """A small real DOCX, with fixed ZIP timestamps for stable source SHA256."""
    paragraphs = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{escape(line)}</w:t></w:r></w:p>'
        for line in text.splitlines()
    )
    parts = {
        "[Content_Types].xml": (
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.document.main+xml"/></Types>'
        ),
        "_rels/.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'officeDocument" Target="word/document.xml"/></Relationships>'
        ),
        "word/document.xml": f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{paragraphs}<w:sectPr/></w:body></w:document>',
    }
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        for name, content in parts.items():
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, content.encode("utf-8"))
    return stream.getvalue()


def build_scenario(scenario: str, knowledge: KnowledgeSnapshot) -> tuple[HandoffSet, bytes]:
    suffix = scenario.upper()
    context = Context(
        ca_id=f"CA_FIXTURE_{suffix}",
        phien_ban_id="DEPLOY_PARALLEL_V1",
        rule_version="RULE_PARALLEL_V1",
        legal_knowledge_version="LEGAL_PARALLEL_V1",
        knowledge_snapshot_sha256=knowledge.sha256,
        run_id=f"RUN_FIXTURE_{suffix}",
        trace_id=f"TRACE_FIXTURE_{suffix}",
    )
    contract_id = f"HD_FIXTURE_{suffix}"
    chunk_id = f"D_FIXTURE_{suffix}"
    fields = {
        "loai_hop_dong_id": "MB_CAN_HO_CHUNG_CU",
        "linh_vuc": "NHA_O",
        "he_phap_luat": "VIET_NAM",
        "muc_dich_giao_dich": "TIEU_DUNG_KHONG_THUONG_MAI",
        "la_hop_dong_theo_mau": True,
    }
    if scenario != "unknown_version":
        fields["ngay_giao_ket"] = "2026-01-15"
    legal_document_id = "VBPL008" if scenario == "stale_citation" else "VBPL001"
    legal_document = knowledge.documents[legal_document_id]
    citation_text = f"Viện dẫn minh họa: {legal_document['so_hieu']}."
    text = "\n".join(
        [
            "DỮ LIỆU TỔNG HỢP ĐỂ KIỂM TRA WIRING, KHÔNG PHẢI HỢP ĐỒNG THẬT.",
            json.dumps(fields, ensure_ascii=False),
            "Nội dung minh họa; proposed findings và gates là fixture, chưa kiểm chứng.",
            citation_text,
        ]
    )
    source = docx_bytes(text)
    case = AssessmentCase(
        ca_id=context.ca_id,
        hop_dong_id=contract_id,
        source={
            "tep_id": f"TEP_{suffix}",
            "object_uri": f"fixture://parallel/{scenario}/source.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "sha256": hashlib.sha256(source).hexdigest(),
        },
        assessment_context={"ngay_danh_gia": "2026-01-15"},
        deployment={
            key: getattr(context, key)
            for key in ("phien_ban_id", "rule_version", "legal_knowledge_version")
        },
        tenant_id="TENANT_FIXTURE",
        created_by="USER_FIXTURE",
    )
    evidence = {
        "doan_id": chunk_id,
        "trich_dan": text,
        "ky_tu_bat_dau": 0,
        "ky_tu_ket_thuc": len(text),
    }
    profile = ContractProfile(
        hop_dong_id=contract_id,
        profile=fields,
        evidence=[{"bang_chung_id": "BC_PROFILE", **evidence}],
        facts=[
            {
                "trich_xuat_id": f"TX_{key}",
                "ten_truong": f"profile.{key}",
                "gia_tri_raw": str(value),
                "gia_tri_chuan_json": value,
                "trang_thai": "SYNTHETIC_UNVERIFIED",
                "phuong_phap": "FIXTURE",
                "human_verified": False,
                "evidence_ids": ["BC_PROFILE"],
            }
            for key, value in fields.items()
        ],
        time_markers=[]
        if scenario == "unknown_version"
        else [
            {
                "moc_id": "M_GIAO_KET",
                "loai_moc": "NGAY_GIAO_KET",
                "ngay": "2026-01-15",
                "gia_tri_raw": "2026-01-15",
                "do_chinh_xac": "NGAY",
                "trang_thai": "SYNTHETIC_UNVERIFIED",
                "duoc_dung_phan_giai": True,
                "trich_xuat_id": "TX_ngay_giao_ket",
            }
        ],
    )
    extracted_citation = CitationExtraction(
        vien_dan_id="VD_FIXTURE",
        hop_dong_id=contract_id,
        raw_text=citation_text,
        normalized={
            "so_hieu": legal_document["so_hieu"],
            "ten_van_ban": legal_document["ten_van_ban"],
        },
        extraction={"status": "EXTRACTED", "confidence": 1},
        evidence=[{"doan_id": chunk_id, "page_start": 1, "page_end": 1}],
    )
    document = DocumentIntelligenceResult(
        contract_profile=profile,
        chunks=[
            {
                "doan_id": chunk_id,
                "hop_dong_id": contract_id,
                "noi_dung": text,
                "page_start": 1,
                "page_end": 1,
            }
        ],
        citations=[extracted_citation],
    )
    version = knowledge.versions["PV_GYC005"]
    scope = ScopeResolution(
        yeu_cau_ca_id="YCCA_FIXTURE",
        ca_id=context.ca_id,
        requirement_id=version["requirement_id"],
        nhom_phien_ban=version["nhom_phien_ban"],
        scope_status="MATCH",
        scope_reason="Synthetic scope, not a legal determination",
        profile_snapshot_json=profile.model_dump(mode="json"),
    )
    unresolved = scenario == "unknown_version"
    requirement = ApplicableRequirement(
        **scope.model_dump(exclude={"scope_reason"}),
        requirement_version_id=None if unresolved else version["requirement_version_id"],
        version_status="UNKNOWN" if unresolved else "RESOLVED",
        applicability_status="UNKNOWN" if unresolved else "CONFIRMED",
        moc_ap_dung=None if unresolved else "2026-01-15",
        moc_id=None if unresolved else "M_GIAO_KET",
        loai_moc="NGAY_GIAO_KET",
        phien_ban_id=context.phien_ban_id,
        reason={"fixture": "No relevant date" if unresolved else "Synthetic pinned version"},
    )
    citation = CitationValidation(
        finding_id="CF_FIXTURE",
        ca_id=context.ca_id,
        vien_dan_id=extracted_citation.vien_dan_id,
        normalized_van_ban_id=legal_document_id,
        relevant_date="2026-01-15",
        status="STALE" if scenario == "stale_citation" else "VALID",
        reason_code="SYNTHETIC_FIXTURE",
        ly_do="Synthetic citation findings, not human verified",
        domain_status="MATCH",
        finding_verified=True,
        current_status=legal_document["trang_thai"],
        replacement_van_ban_id=legal_document.get("van_ban_thay_the_id"),
        source_snapshot_json={
            "fixture_only": True,
            "notice": NOTICE,
            "reviewed_knowledge": True,
            "identity_confirmed": True,
            "temporal_source_complete": True,
            "transition_context_resolved": True,
            "evidence_ids": [chunk_id],
        },
        lan_chay_id=context.run_id,
        knowledge_version=context.legal_knowledge_version,
    )
    retrieval = []
    observations = []
    desired_findings = EXPECTED[scenario][1]
    for index, criterion in enumerate(knowledge.criteria_for(requirement.requirement_version_id)):
        finding = desired_findings[index]
        has_evidence = scenario != "insufficient_evidence"
        if has_evidence:
            retrieval.append(
                {
                    "truy_xuat_id": f"RTX_FIXTURE_{index}",
                    "yeu_cau_ca_id": requirement.yeu_cau_ca_id,
                    "tieu_chi_id": criterion["tieu_chi_id"],
                    "doan_id": chunk_id,
                    "thu_hang": 1,
                    "duoc_chon": True,
                    "scores": {"fixture": 1.0},
                    "retrieval_version": "FIXTURE_NO_SEARCH",
                    "index_version": "FIXTURE_NO_INDEX",
                    "lan_chay_id": context.run_id,
                }
            )
        observations.append(
            {
                "tieu_chi_id": criterion["tieu_chi_id"],
                "proposed_finding": "SATISFIED" if finding == "UNKNOWN" else finding,
                "giai_thich": "Synthetic observation; verification gates are fixture inputs",
                "gates": {
                    "coverage_complete": has_evidence,
                    "absence_verified": has_evidence,
                    "evidence_validated": has_evidence,
                    "source_verified": True,
                    "scope_confirmed": True,
                    "version_resolved": True,
                    "exceptions_resolved": True,
                },
                "evidence": [evidence] if has_evidence and finding != "MISSING" else [],
                "local_applicability": "MATCH",
                "mandatory_confirmed": True,
                "all_pages_readable": has_evidence,
                "all_related_documents_received": has_evidence,
                "model_version": "FIXTURE_STRUCTURED_NO_LLM",
            }
        )
    reasoning = ReasoningRequest(
        **context.model_dump(),
        payload=ReasoningPayload(
            hop_dong_id=contract_id,
            requirements=[requirement],
            chunks=document.chunks,
            retrieval=retrieval,
            observations=observations,
        ),
    )
    legal = LegalOutput(scope=[scope], requirements=[requirement], citations=[citation])
    compliance = evaluate_compliance(reasoning, knowledge)
    integration = IntegrationInput(
        context=context, case=case, document=document, legal=legal, compliance=compliance
    )
    # Use the same canonical pipeline input as consumers; timestamps are fixed for regeneration.
    response = evaluate(
        PipelineRequest(
            **context.model_dump(),
            payload={**reasoning.payload.model_dump(), "citations": legal.citations},
        ),
        knowledge,
    )
    response.produced_at = datetime(2026, 10, 13, tzinfo=timezone.utc)
    handoffs = HandoffSet(
        document_input=DocumentInput(context=context, case=case),
        document_output=document,
        scope_input=ScopeInput(context=context, contract_profile=profile),
        temporal_input=TemporalInput(context=context, contract_profile=profile, scope=legal.scope),
        citation_input=CitationInput(
            context=context,
            contract_profile=profile,
            citations=document.citations,
            chunks=document.chunks,
        ),
        legal_output=legal,
        retrieval_input=RetrievalInput(
            context=context,
            hop_dong_id=contract_id,
            requirements=legal.requirements,
            chunks=document.chunks,
        ),
        retrieval_output=reasoning.payload.retrieval,
        compliance_input=reasoning,
        compliance_output=compliance,
        integration_input=integration,
        pipeline_output=response,
        report_output=build_draft_report(integration, knowledge),
    )
    validate_handoffs(handoffs, knowledge)
    return handoffs, source


def write_fixtures(root: Path, knowledge: KnowledgeSnapshot):
    for scenario in SCENARIOS:
        directory = root / scenario
        directory.mkdir(parents=True, exist_ok=True)
        handoffs, source = build_scenario(scenario, knowledge)
        (directory / "source.docx").write_bytes(source)
        for name in HandoffSet.model_fields:
            (directory / f"{name}.json").write_text(
                json_text(getattr(handoffs, name)), encoding="utf-8"
            )
        status, findings, compliance, citation, verification = EXPECTED[scenario]
        manifest = FixtureManifest(
            scenario=scenario,
            notice=NOTICE,
            knowledge_snapshot_sha256=knowledge.sha256,
            files={
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(directory.iterdir())
                if path.name
                in {f"{name}.json" for name in HandoffSet.model_fields} | {"source.docx"}
            },
            expected={
                "requirement_status": status,
                "criterion_findings": findings,
                "compliance_risks": compliance,
                "citation_risks": citation,
                "verification_risks": verification,
            },
        )
        (directory / "manifest.json").write_text(json_text(manifest), encoding="utf-8")
