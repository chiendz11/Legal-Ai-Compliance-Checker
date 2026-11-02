"""Demo C07: xem kết quả tham chiếu rồi thử nhận định thủ công trong run DEV.

Chạy từ thư mục gốc dự án:
    python -m legal_checker.modules.compliance.demo_c07

Đọc main() trước, rồi xem từng hàm bên trên. Demo dùng snapshot đã được setup.
Run DEV có C06 chọn bằng tay và Observation nháp; các xác minh còn thiếu giữ UNKNOWN.
C06/C07 của bản DEV chỉ nằm trong bộ nhớ và được in ra terminal.
"""

from uuid import uuid4

from legal_checker.core.config import Settings
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.manual_observations import build_reviewed_observation
from legal_checker.modules.compliance.mappers import map_chunk, map_requirement, map_retrieval
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.modules.retrieval.repository import RetrievalDatasetRepository
from legal_checker.shared.contracts.document_intelligence import Evidence
from legal_checker.shared.contracts.reasoning import (
    CriterionResult,
    ReasoningRequest,
)
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.shared.validation import validate_request

CASE_ID = "CA360_001"
RUN_ID = "CA360_001_PDF360_LS2_REFERENCE"
CRITERION_ID = "TC_PV_HYC049_01"
CANDIDATE_CHUNK_ID = "HD360_001_LS2_C00286"


def prepare_request(database_url: str) -> tuple[ReasoningRequest, list[dict]]:
    """Đọc DB và ghép dữ liệu thành đầu vào cho reasoner C07.

    Đầu vào: chuỗi kết nối PostgreSQL; case/run lấy từ các hằng số đầu file.
    Trả về: request đã map đúng kiểu dữ liệu và các dòng C06 gốc chưa lọc.
    Request giữ mọi C05, chỉ nhận C06 FINAL được chọn và chưa có Observation.
    Các dòng C06 gốc được giữ riêng để giải thích vì sao evidence chưa được chọn.
    """
    repository = RetrievalDatasetRepository(database_url)
    source = repository.load_input_rows(CASE_ID)
    case = source["case"]
    retrieval_rows = repository.load_seeded_evidence(CASE_ID, RUN_ID)

    with connect_postgres(database_url) as connection:
        manifest = connection.execute(
            """
            SELECT knowledge_snapshot_sha256 FROM qa.case_manifest
            WHERE case_id=%s AND hop_dong_id=%s
            """,
            (case["ca_id"], case["hop_dong_id"]),
        ).fetchone()
    if not manifest or not manifest["knowledge_snapshot_sha256"]:
        raise ValueError(f"Không tìm thấy knowledge snapshot của case {CASE_ID}")

    request = ReasoningRequest(
        ca_id=case["ca_id"],
        phien_ban_id=case["phien_ban_id"],
        rule_version=case["rule_version"],
        legal_knowledge_version=case["legal_knowledge_version"],
        knowledge_snapshot_sha256=manifest["knowledge_snapshot_sha256"],
        run_id=RUN_ID,
        trace_id=str(uuid4()),
        payload={
            "hop_dong_id": case["hop_dong_id"],
            # Giữ mọi C05, kể cả UNKNOWN hoặc chưa có evidence.
            "requirements": [map_requirement(row) for row in source["requirements"]],
            "chunks": [map_chunk(row) for row in source["chunks"]],
            "retrieval": [
                map_retrieval(row)
                for row in retrieval_rows
                if row["duoc_chon"] is True and row["giai_doan"] == "FINAL"
            ],
            # Nhận định và gates đã xác minh sẽ được bổ sung ở bước sau.
            "observations": [],
        },
    )
    return request, retrieval_rows


def build_candidate_evidence(request: ReasoningRequest) -> Evidence | None:
    """Tạo evidence ứng viên từ nguyên văn đoạn C00286 trong request.

    Đầu vào: request có danh sách các đoạn hợp đồng đã đọc từ DB.
    Trả về: Evidence với quote và vị trí ký tự, hoặc None nếu không có đoạn này.
    Evidence chỉ để đọc/đối chiếu; việc chọn C06 và tạo Observation là bước riêng.
    """
    chunk = next(
        (chunk for chunk in request.payload.chunks if chunk.doan_id == CANDIDATE_CHUNK_ID),
        None,
    )
    if chunk is None:
        return None
    return Evidence(
        doan_id=chunk.doan_id,
        trich_dan=chunk.noi_dung,
        ky_tu_bat_dau=0,
        ky_tu_ket_thuc=len(chunk.noi_dung),
    )


def build_dev_request(
    reference_request: ReasoningRequest,
    evidence: Evidence | None,
    knowledge: KnowledgeSnapshot,
    *,
    include_observation: bool = False,
) -> ReasoningRequest:
    """Tạo bản thử riêng cho criterion đích từ evidence đã đọc bằng tay.

    Đầu vào: request tham chiếu, evidence C00286 và snapshot đã nạp.
    Trả về: request DEV có run/trace riêng, giữ C05/Chunk/pin và một C06 chọn bằng tay.
    include_observation=True thêm nhận định nháp; nguồn/ngoại lệ vẫn chờ xác minh.
    Hàm chỉ tạo dữ liệu trong bộ nhớ; request tham chiếu được dùng để sao chép.
    """
    validate_request(reference_request, knowledge)
    if evidence is None or evidence.doan_id != CANDIDATE_CHUNK_ID:
        raise ValueError(f"Cần evidence ứng viên từ đoạn {CANDIDATE_CHUNK_ID}")

    # 1. Tìm đúng criterion và C05 chứa phiên bản của criterion đó.
    criterion = knowledge.criteria.get(CRITERION_ID)
    if criterion is None:
        raise ValueError(f"Không tìm thấy criterion {CRITERION_ID} trong snapshot")
    requirements = [
        item
        for item in reference_request.payload.requirements
        if item.requirement_version_id == criterion["requirement_version_id"]
    ]
    if len(requirements) != 1:
        raise ValueError("Cần đúng một C05 cho phiên bản của criterion đang chọn")
    requirement = requirements[0]

    # 2. Kiểm tra quote và vị trí ký tự trên nguyên văn chunk.
    chunk = next(
        (item for item in reference_request.payload.chunks if item.doan_id == evidence.doan_id),
        None,
    )
    if chunk is None:
        raise ValueError("Evidence không thuộc các đoạn hợp đồng đã đọc")
    start, end = evidence.ky_tu_bat_dau, evidence.ky_tu_ket_thuc
    if (
        not 0 <= start < end <= len(chunk.noi_dung)
        or chunk.noi_dung[start:end] != evidence.trich_dan
    ):
        raise ValueError("Quote hoặc vị trí ký tự không khớp với chunk")

    # 3. Ghi nhận lựa chọn bằng tay, dùng ID/run riêng và không gán điểm tìm kiếm.
    dev_run_id = f"{reference_request.ca_id}_DEV_MANUAL_{uuid4().hex}"
    manual_c06 = RetrievalEvidence(
        truy_xuat_id=f"C06_MANUAL_{uuid4().hex}",
        yeu_cau_ca_id=requirement.yeu_cau_ca_id,
        tieu_chi_id=CRITERION_ID,
        doan_id=evidence.doan_id,
        giai_doan="FINAL",
        thu_hang=1,
        duoc_chon=True,
        scores={},
        query_text=f"MANUAL_REVIEW: {CRITERION_ID}",
        retrieval_version="MANUAL_SELECTION_DEMO_V1",
        index_version="MANUAL_NO_INDEX",
        lan_chay_id=dev_run_id,
    )

    # 4. Nhận định nháp về nội dung; các gates chỉ phản ánh việc đã kiểm tra.
    observations = []
    if include_observation:
        observations.append(build_reviewed_observation(criterion, requirement, [evidence]))

    # 5. Bản DEV chỉ chọn evidence cho criterion đang học; kiểm tra lại DTO đầy đủ.
    data = reference_request.model_dump()
    data["run_id"] = dev_run_id
    data["trace_id"] = str(uuid4())
    data["payload"]["retrieval"] = [manual_c06.model_dump()]
    data["payload"]["observations"] = [item.model_dump() for item in observations]
    dev_request = ReasoningRequest.model_validate(data)
    validate_request(dev_request, knowledge)
    return dev_request


def print_summary(
    request: ReasoningRequest,
    retrieval_rows: list[dict],
    candidate_evidence: Evidence | None,
    results: list[CriterionResult],
) -> None:
    """In dữ liệu và kết quả của criterion đang học để kiểm tra trên terminal.

    Đầu vào: request đã kiểm tra, C06 gốc, evidence ứng viên và danh sách C07.
    Hiển thị bốn nhóm: đầu vào, C06, evidence ứng viên và kết quả criterion đích.
    Trả về None; hàm chỉ in thông tin, không tạo nhận định hay lưu kết quả vào DB.
    """
    print("\n1. ĐẦU VÀO THAM CHIẾU")
    print("Case:", request.ca_id, "| Run:", request.run_id)
    print("C05:", len(request.payload.requirements), "| Chunks:", len(request.payload.chunks))
    print("Snapshot:", request.knowledge_snapshot_sha256)
    print("Observations:", len(request.payload.observations), "| Kiểm tra liên kết: OK")

    print("\n2. C06 CỦA CRITERION:", CRITERION_ID)
    candidates = [row for row in retrieval_rows if row["tieu_chi_id"] == CRITERION_ID]
    selected = [row for row in request.payload.retrieval if row.tieu_chi_id == CRITERION_ID]
    print("Trước lọc:", len(candidates), "| Được chọn FINAL:", len(selected))
    for row in candidates:
        print(f"  {row['doan_id']} | {row['giai_doan']} | duoc_chon={row['duoc_chon']}")

    print("\n3. EVIDENCE ỨNG VIÊN")
    if candidate_evidence is None:
        print("Không tìm thấy đoạn:", CANDIDATE_CHUNK_ID)
    else:
        chunk = next(
            chunk for chunk in request.payload.chunks if chunk.doan_id == candidate_evidence.doan_id
        )
        start = candidate_evidence.ky_tu_bat_dau
        end = candidate_evidence.ky_tu_ket_thuc
        print("Đoạn:", candidate_evidence.doan_id, "| Vị trí:", start, end)
        print("Quote khớp:", chunk.noi_dung[start:end] == candidate_evidence.trich_dan)
        print(candidate_evidence.trich_dan)
        print("Đây là ứng viên đọc thêm; chưa được gắn vào C06 được chọn hoặc Observation.")

    print("\n4. KẾT QUẢ C07 THAM CHIẾU")
    print("Tổng số kết quả:", len(results))
    target_result = next((item for item in results if item.tieu_chi_id == CRITERION_ID), None)
    if target_result is None:
        print("Chưa có C07 cho criterion này; kiểm tra phiên bản yêu cầu trong C05.")
    else:
        print("Criterion:", target_result.tieu_chi_id)
        print("Finding:", target_result.finding, "| Review:", target_result.review_status)
        print("Giải thích:", target_result.uncertainty_reason or target_result.giai_thich)
    print("Kết quả được in ra terminal; demo chưa lưu C07 vào DB.")


def main() -> None:
    """Điều phối toàn bộ demo theo sáu bước được đánh số bên dưới.

    Đọc cấu hình từ .env, chuẩn bị request/evidence, nạp snapshot rồi gọi reason().
    Sau bản tham chiếu, thử một Observation thủ công bằng request DEV riêng.
    Trả về None; các kết quả được hiển thị trên terminal.
    Bắt đầu đọc hàm này để thấy thứ tự chạy trước khi xem từng hàm chi tiết.
    """
    settings = Settings.from_env()

    # 1. Đọc DB và chuẩn bị request: C05 + chunks + C06 được chọn.
    request, retrieval_rows = prepare_request(settings.database_url)

    # 2. Chuẩn bị evidence ứng viên để đọc riêng, chưa đưa vào request.
    candidate_evidence = build_candidate_evidence(request)

    # 3. Nạp đúng snapshot đã lưu và kiểm tra các liên kết đầu vào.
    knowledge = Knowledge(
        settings.database_url,
        snapshot_sha256=request.knowledge_snapshot_sha256,
    )

    criterion = knowledge.criteria[CRITERION_ID]

    print("\nĐIỀU KIỆN ÁP DỤNG CỦA CRITERION")
    print("Nội dung:", criterion.get("noi_dung"))
    print("Phạm vi:", criterion.get("pham_vi_ap_dung_chi_tiet"))
    print("Điều kiện:", criterion.get("dieu_kien"))
    print("Ngoại lệ cần xét:", criterion.get("ngoai_le_can_xet"))

    validate_request(request, knowledge)

    # 4. Reasoner kiểm tra request; observations rỗng nên các C07 là UNKNOWN.
    results = reason(request, knowledge)

    # 5. Xem dữ liệu và kết quả của criterion đang học.
    print_summary(request, retrieval_rows, candidate_evidence, results)

    # 6. Tạo C06/Observation nháp trong DEV rồi đánh giá lại criterion đích.
    if candidate_evidence is None:
        print("Chưa tạo bản DEV vì không tìm thấy evidence ứng viên.")
        return
    dev_request = build_dev_request(
        request,
        candidate_evidence,
        knowledge,
        include_observation=True,
    )
    dev_results = reason(dev_request, knowledge)
    print("\n5. KẾT QUẢ C07 DEV CHỌN BẰNG TAY")
    print("Nguồn tham chiếu:", request.run_id)
    print("Run DEV:", dev_request.run_id)
    print("C06 được chọn:", len(dev_request.payload.retrieval))
    print("Observations:", len(dev_request.payload.observations))
    print("Đề xuất:", dev_request.payload.observations[0].proposed_finding)
    for result in dev_results:
        if result.tieu_chi_id == CRITERION_ID:
            print("Finding:", result.finding, "| Review:", result.review_status)
            print("Lý do:", result.uncertainty_reason)
    print("C06/C07 DEV chỉ nằm trong bộ nhớ.")


if __name__ == "__main__":
    main()
