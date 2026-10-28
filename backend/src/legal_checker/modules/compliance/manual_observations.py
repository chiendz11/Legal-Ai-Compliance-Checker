"""Đóng gói nhận định đã đối chiếu thủ công cho ví dụ phí bảo trì C07."""

from collections.abc import Mapping, Sequence
from typing import Any

from legal_checker.shared.contracts.document_intelligence import Evidence
from legal_checker.shared.contracts.reasoning import Gates, Observation
from legal_checker.shared.contracts.temporal import ApplicableRequirement

REVIEWED_CRITERION_ID = "TC_PV_HYC049_01"


def build_reviewed_observation(
    criterion: Mapping[str, Any],
    requirement: ApplicableRequirement,
    evidence: Sequence[Evidence],
) -> Observation:
    """Tạo một Observation nháp từ nhận định thủ công của criterion phí bảo trì.

    Đầu vào: criterion trong snapshot, C05 tương ứng và các evidence đã đối chiếu.
    Bên gọi đã xác nhận evidence hỗ trợ predicate về điều khoản, mức phí và căn cứ
    tính; đã kiểm tra quote/offset trên chunk và chọn C06 cho cùng criterion/run.
    Ba tham số này không đủ để hàm tự kiểm chứng nguyên văn hoặc liên kết C06.

    Hàm chỉ đóng gói đề xuất SATISFIED cho TC_PV_HYC049_01, không tự diễn giải
    predicate hay tìm từ khóa. Phạm vi riêng, nguồn và ngoại lệ vẫn chưa xác minh.
    Evidence được sao chép, giữ nguyên text/offset; reason() sẽ kiểm tra lại đầu vào.
    Trả về Observation trong bộ nhớ; không đọc DB hay thay đổi dữ liệu được truyền vào.
    """
    if criterion.get("tieu_chi_id") != REVIEWED_CRITERION_ID:
        raise ValueError(f"Nhận định thủ công này chỉ hỗ trợ {REVIEWED_CRITERION_ID}")
    if criterion.get("loai_kiem_tra") != "CONTRACT_CONTENT":
        raise ValueError("Nhận định này chỉ hỗ trợ criterion CONTRACT_CONTENT")

    version_id = criterion.get("requirement_version_id")
    if not version_id or version_id != requirement.requirement_version_id:
        raise ValueError("Criterion và C05 phải có cùng phiên bản yêu cầu đã xác định")
    if not evidence:
        raise ValueError("Cần ít nhất một evidence đã đối chiếu với predicate")

    # Tạo Evidence mới để không dùng chung đối tượng có thể bị sửa bởi bên gọi.
    # Validation ở đây kiểm tra DTO; đối chiếu text và C06 vẫn thuộc bên gọi/reason().
    reviewed_evidence = [Evidence.model_validate(item.model_dump()) for item in evidence]

    explanation = (
        "Nhận định thủ công: evidence đã được đối chiếu với predicate về điều khoản "
        "kinh phí bảo trì, mức phí (tỷ lệ hoặc số tiền) và căn cứ tính. "
        "Đề xuất SATISFIED chỉ xét nội dung criterion hiện tại. "
        "Phạm vi áp dụng riêng, nguồn pháp lý và các ngoại lệ chưa được xác minh đầy đủ."
    )
    if requirement.profile_snapshot_json.get("synthetic") is True:
        explanation += (
            " Snapshot C05 được đánh dấu synthetic; nhận định phục vụ kiểm thử, "
            "chưa xác minh giao dịch thực tế."
        )
    if not requirement.confirmed:
        explanation += " C05 chưa xác nhận đầy đủ phạm vi/phiên bản áp dụng."

    return Observation(
        tieu_chi_id=REVIEWED_CRITERION_ID,
        proposed_finding="SATISFIED",
        giai_thich=explanation,
        evidence=reviewed_evidence,
        local_applicability="UNKNOWN",
        gates=Gates(
            # Ghi nhận việc đối chiếu thủ công theo tiền điều kiện của hàm.
            evidence_validated=True,
            scope_confirmed=requirement.scope_status == "MATCH",
            version_resolved=requirement.version_status == "RESOLVED",
            source_verified=False,
            exceptions_resolved=False,
        ),
        model_version="MANUAL_DEV_NO_LLM",
        prompt_version="NOT_USED",
    )
