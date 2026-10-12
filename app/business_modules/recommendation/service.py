from app.contracts.common import Context
from app.contracts.recommendation import Recommendation
from app.contracts.risk import RiskResult
from app.contracts.temporal import ApplicableRequirement
from app.shared.ids import stable_id
from app.workflows.interfaces.knowledge import KnowledgeSnapshot


def recommend(
    request: Context,
    knowledge: KnowledgeSnapshot,
    risks: list[RiskResult],
    requirements: list[ApplicableRequirement],
):
    results = []
    for risk in risks:
        links = [
            r for r in knowledge.tables["rui_ro_khuyen_nghi"] if r["rui_ro_id"] == risk.rui_ro_id
        ]
        for link in links:
            template = knowledge.recommendations[link["khuyen_nghi_id"]]
            verification = risk.risk_type == "VERIFICATION" or not risk.legal_basis_ids
            action = "REQUEST_VERIFICATION" if verification else template["loai_hanh_dong"]
            content = template["noi_dung"]
            if verification and template["gap_type"] != "UNKNOWN":
                content = (
                    "Cần xác minh nguồn pháp lý và căn cứ cho "
                    + risk.risk_snapshot["ten_rui_ro"]
                    + ". Chưa đủ căn cứ đề xuất sửa điều khoản."
                )
            results.append(
                Recommendation(
                    khuyen_nghi_ca_id=stable_id(
                        request, "KN", risk.ket_qua_rui_ro_id + template["khuyen_nghi_id"]
                    ),
                    ket_qua_rui_ro_id=risk.ket_qua_rui_ro_id,
                    khuyen_nghi_id=template["khuyen_nghi_id"],
                    noi_dung=content,
                    loai_hanh_dong=action,
                    # Preserve the severity chosen by the Risk Engine.
                    uu_tien=risk.severity,
                    dieu_kien_snapshot={
                        "source": risk.source.model_dump(),
                        "risk_type": risk.risk_type,
                        "risk": risk.risk_snapshot,
                        "rule": risk.rule_snapshot_json,
                        "profile": [
                            r.profile_snapshot_json
                            for r in requirements
                            if r.yeu_cau_ca_id == risk.source.yeu_cau_ca_id
                        ],
                        "verification_required": verification,
                    },
                    evidence_ids=risk.evidence_ids,
                    legal_basis_ids=risk.legal_basis_ids,
                    template_snapshot_json=template,
                    rule_version=request.rule_version,
                    knowledge_snapshot_sha256=request.knowledge_snapshot_sha256,
                )
            )
    return results
