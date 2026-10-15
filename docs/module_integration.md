# Nối module theo BRD v1.1

Backend nằm ở `backend/src/legal_checker/`. Contracts ở `shared/contracts/`, nghiệp vụ/repository ở `modules/`, điều phối ở `workflows/`; `core` cung cấp cấu hình/kết nối DB.

| Bước | Module | Bàn giao | Trạng thái |
|---|---|---|---|
| 1–2 | documents | C01, C02 + chunks, C03 | Interfaces/skeleton |
| 3A | applicable_law | C04 → C05 | Interfaces/skeleton |
| 3B | citation_validation | C09 | Interfaces/skeleton |
| 4 | retrieval | C06 theo criterion | Interfaces/skeleton + repository đọc seed |
| 5 | compliance | C07 → C08 | Skeleton, implementation cũ đã xóa |
| 6 | risks | C10 từ compliance/citation | Skeleton, implementation cũ đã xóa |
| 7 | recommendations | C11 | Skeleton, implementation cũ đã xóa |
| 8 | reviews | C12 | Interfaces |
| 9 | reports | C13 | Helper ghép draft; reader/writer/export/UI cần triển khai |

`DraftAssessmentWorkflow` giữ wiring/pin/checks upstream khi inject implementations; hiện dừng với `NotImplementedError` ở bước 5. Không có factory full-system mặc định hoặc đánh giá thành công. `workflows/steps_5_7.evaluate`, services và validators bước 5–7 đều là stub.

Các POST chạy riêng module trong `/api/v1` đã xóa. Các module trao đổi DTO qua hàm Python;
GET knowledge và run vẫn hoạt động. API khởi chạy assessment toàn bộ chưa triển khai.

Nhóm A/B/C đọc input mẫu từ DB local riêng, map đúng DTO rồi tự triển khai module; dữ liệu output seed là reference của release đã dựng trước đây, không phải output của implementation hiện tại. Chọn đúng case/run/hash, không ghi đè run tham chiếu khi thử nghiệm. Xem [query/JOIN theo nhóm](huong_dan_trien_khai_module_sau_seed.md).

`report_input_from_draft` giữ handoff compliance-only của nhóm C cũ. Khi report nhận full C10/C11 từ workflow, truyền chúng riêng:

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

`main.create_app` khởi tạo Knowledge/Store qua `api/dependencies.build_services`. Có thể inject `Services(knowledge, memory_store)` trong tests. Không còn `app` hoặc import chuyển tiếp.

Tests nền tảng kiểm tra schema, upstream ownership/provenance, snapshots, transaction/rollback, đọc run và việc các route module nội bộ không được công khai. Các tests dựa vào engine cũ đã bỏ; người triển khai bước 5–7 cần viết bộ tests riêng. [Trạng thái chi tiết](architecture.md#trạng-thái-skeleton-bước-57).
