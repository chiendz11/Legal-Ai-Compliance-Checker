# Nối module theo BRD v1.1

Backend nằm ở `backend/src/legal_checker/`. Contracts ở `shared/contracts/`, nghiệp vụ/repository ở `modules/`, điều phối ở `workflows/`; `core` cung cấp cấu hình/kết nối DB.

| Bước | Module | Bàn giao | Trạng thái |
|---|---|---|---|
| 1–2 | documents | C01, C02 + chunks, C03 | Interfaces/skeleton |
| 3A | applicable_law | C04 → C05 | Interfaces/skeleton |
| 3B | citation_validation | C09 | Interfaces/skeleton |
| 4 | retrieval | C06 theo criterion | Interfaces/skeleton + repository đọc seed |
| 5 | compliance | C07 → C08 | Provider/review/grounding, numeric rules và AGG_CAN_HO_V1 đã triển khai |
| 6 | risks | C10 từ compliance/citation | Hai mappers độc lập, policy guards, XOR source và dedup đã triển khai |
| 7 | recommendations | C11 | Template engine/validator/service đã triển khai, luôn PENDING |
| 8 | reviews | C12 | Interfaces |
| 9 | reports | C13 | Helper ghép draft; reader/writer/export/UI cần triển khai |

`DraftAssessmentWorkflow` giữ wiring/pin/checks upstream và chạy C07 → C08 → C10 → C11
khi nhận implementations được inject. Không có factory full-system mặc định hoặc
upstream giả. Retrieval/Observation/Citation vắng mặt tường minh giữ diagnostics,
UNKNOWN/INSUFFICIENT hoặc NOT_RUN; external evidence registry phải do backend cung cấp
độc lập. `workflows.steps_5_7.evaluate` là pipeline đầy đủ nhận C09, còn
`compliance.service.evaluate_compliance` chỉ xử lý compliance-sourced C10/C11.

Các POST chạy riêng module trong `/api/v1` đã xóa. Các module trao đổi DTO qua hàm Python;
GET knowledge và run vẫn hoạt động. API khởi chạy assessment toàn bộ chưa triển khai.

Nhóm A/B đọc input mẫu từ DB local riêng, map đúng DTO rồi triển khai upstream; nhóm C
nhận các handoffs đó để chạy engines đã có. Dữ liệu output seed là reference của release
trước đây, không phải output mới của implementation hiện tại. Chọn đúng case/run/hash,
không ghi đè run tham chiếu. [Query/JOIN theo nhóm](huong_dan_trien_khai_module_sau_seed.md)
và [bàn giao nhóm C](group_c_handoff.md) ghi rõ nguồn và giới hạn.

`report_input_from_draft` giữ handoff compliance-only cùng diagnostics. Khi report nhận
full C10/C11 đã hợp nhất từ workflow hoặc run đã lưu, truyền chúng riêng:

```python
report = build_draft_report(
    integration_input,
    knowledge,
    risks=merged_c10,
    recommendations=merged_c11,
)
validate_report(
    integration_input,
    report,
    knowledge,
    risks=merged_c10,
    recommendations=merged_c11,
)
```

Report chỉ ghép và kiểm tra dữ liệu được cung cấp, không tính lại risk hoặc recommendation. Caller phải đọc C10/C11 của đúng run. Report vẫn DRAFT/PENDING khi chưa có review.

```python
from legal_checker.modules.assessments.repository import Store

store = Store(database_url)
request = store.get_input(case_id, run_id)
response = store.get(case_id, run_id)
lineage = store.get_lineage(case_id, run_id)
if request is None or response is None:
    raise ValueError("Run chưa có kết quả đã lưu")
merged_c10 = response.payload.risks
merged_c11 = response.payload.recommendations
```

Các đường đọc kiểm tra case/run membership, checksums, pins, pinned knowledge,
normalized rows và lineage, không gọi engines. Dữ liệu legacy thiếu provenance hoặc
lineage giữ lỗi tường minh; không ghép theo “run mới nhất” hoặc QA EXPECTED. C09 thiếu
provenance có diagnostics và không tạo risk khẳng định; không nâng UNKNOWN thành vi phạm.

Runner `python -m legal_checker.modules.assessments.run_group_c` hỗ trợ offline/replay,
`--save`, `--read-run` và export atomic vào thư mục mới. [Các lệnh PowerShell](../backend/src/legal_checker/modules/compliance/README.md#runner-nhóm-c-bước-57)
không mặc định gọi API trả phí.

`main.create_app` khởi tạo Knowledge/Store qua `api/dependencies.build_services`. Có thể inject `Services(knowledge, memory_store)` trong tests. Không còn `app` hoặc import chuyển tiếp.

Tests nghiệp vụ C07/C08/C10/C11, workflow/CLI và PostgreSQL kiểm tra source ownership,
snapshots, rollback/retry/concurrency, history/tampering và read không recompute.
Full checks và bằng chứng demo được ghi tại [bàn giao nhóm C](group_c_handoff.md).
[Trạng thái chi tiết](architecture.md#trạng-thái-triển-khai-bước-57).
