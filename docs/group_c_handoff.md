# Bàn giao nhóm C: C07 → C08 → C10 → C11

Nhóm C triển khai các lõi thuần, workflow bước 5–7, runner offline/replay và Store
PostgreSQL. Báo cáo kết quả cuối, lệnh/checks mới và demo nằm trong
[gói hoàn thành](../outputs/group_c_completion_20261029_172537/checklist.md).
Không dùng checkpoints cũ làm bằng chứng cho code cuối.

## Luồng và ranh giới

```text
C02 context + C05 resolved + selected FINAL C06 + chunks/facts/registry + pinned knowledge
  → semantic proposal → backend verification/review độc lập → Observation → C07
  → C08 requirement aggregation
C07 + C09 upstream độc lập → C10 risks → C11 deterministic templates
  → Store transaction → đọc đúng case/run cho nhóm D
```

`reason` không gọi DB/HTTP/LLM. Provider/repository cung cấp dữ liệu; BackendReview
phải gắn exact proposal digest và context, registry giữ nguồn/hash/attestation thật.
Thiếu upstream không được tạo evidence, C06/C09 hoặc review giả. C05 chưa resolve
không sinh criterion giả; C08 vẫn giữ requirement và uncertainty.

`evaluate_compliance(ReasoningRequest, knowledge)` chỉ chạy nhánh compliance.
`workflows.steps_5_7.evaluate(PipelineRequest, knowledge)` nhận thêm C09 để hội tụ
tại C10. `DraftAssessmentWorkflow` ghép các adapters qua DI; registry độc lập là
input trusted backend, không lấy flags từ provider. C09 không sửa C05/C07/C08.

- C07 giữ SATISFIED/VIOLATED/MISSING/UNKNOWN. MISSING cần đủ mandatory, applicability,
  absence/coverage và nguồn tài liệu; retrieval rỗng không chứng minh vắng nội dung.
- C08 dùng AGG_CAN_HO_V1 theo thứ tự policy, không lấy tỷ lệ SATISFIED làm nhãn.
  Thiếu finding/rule/confirmation giữ INSUFFICIENT; N/A chỉ loại có lý do và đủ policy.
- C10 lấy rule/catalog/severity từ knowledge đã pin, một nguồn C07 hoặc C09 theo XOR.
  UNKNOWN chỉ có VERIFICATION khi policy cho phép. C09 thiếu provenance có diagnostic;
  known STALE/INVALID không được tạo risk khẳng định từ nguồn thiếu pin.
- C11 bind theo risk instance, chọn tất cả templates theo policy ALL có thứ tự xác định.
  Policy/facts/elements/limits không hỗ trợ có diagnostics; không tự điền luật, ngày,
  tiền hoặc danh tính. Metadata giữ TEMPLATE_ENGINE_NO_LLM / NOT_USED / PENDING.

## Nhóm D đọc dữ liệu

Chỉ dùng `ca_id` và `run_id` đã chọn. Không lấy run mới nhất và không join toàn bộ
normalized outputs chỉ theo `ca_id`, requirement family hoặc catalog ID.

```python
import os

from legal_checker.modules.assessments.repository import Store

store = Store(os.environ["DATABASE_URL"])
response = store.get(case_id, run_id)
if response is None:
    raise LookupError("Case/run chưa có output đã lưu")
saved_input = store.get_input(case_id, run_id)
lineage = store.get_lineage(case_id, run_id)

criteria = response.payload.criterion_results
requirements = response.payload.requirement_results
risks = response.payload.risks
recommendations = response.payload.recommendations
diagnostics = response.payload.diagnostics
```

Các đường đọc này kiểm tra checksum, ownership, pins, knowledge snapshot, full DTO,
lineage và normalized rows trong transaction nhất quán. Chúng không chạy lại C07,
C08, C10, C11 hoặc provider. Dữ liệu bị sửa/thiếu provenance cần lỗi rõ ràng;
không tự ghép lịch sử hoặc recompute để lấp chỗ trống.

Saved PipelineRequest/Response không đủ để tự dựng toàn bộ C13 IntegrationInput:
C01/C02/C03/C04 gốc còn cần upstream reader có membership đúng run. Profile trong
reasoning provenance có thể chỉ là context tùy chọn; không dựng lại scope hoặc hồ sơ
từ kết luận C07. Builder C13 hiện tại cũng chưa nhúng đầy đủ diagnostics/exclusions
nhóm C vào ReportContent. Nhóm D cần giữ và hiển thị các dữ liệu này riêng; thiếu
C11 do missing template/catalog không đồng nghĩa không cần hành động.

Khi dựng report, dùng DTO đã lưu làm nguồn authoritative, giữ diagnostics, UNKNOWN,
INSUFFICIENT, exclusions và citation branch status. C09 NOT_RUN khác COMPLETED có
danh sách rỗng. Risk type VERIFICATION có thể có nguồn compliance hoặc citation;
phân biệt nhánh bằng `risk.source`/rule snapshot, không suy ra chỉ từ risk type.
Không chạy `evaluate`, `reason`, `evaluate_risks` hoặc `generate_recommendations`
trong report reader. C12 review và C13 publish/export thuộc nhóm khác.

## Mapping DB và lineage

| DTO / mục đích | Bảng/cột chính | Quy tắc đọc |
|---|---|---|
| Context, input/output DTO và hashes | `runtime.assessment_runs`: `(ca_id, run_id)`, `input_json`, `response_json`, `input_sha256`, `output_sha256` | Đọc đúng cặp case/run |
| Deployment/rule/legal/knowledge pin của case | `runtime.assessment_case_pins`: `ca_id`, `knowledge_sha256`, `pin` | Không đổi pin để viết đè lịch sử |
| Membership và full DTO từng output | `runtime.assessment_output_lineage`: `table_name`, `output_id`, `ca_id`, `run_id`, `payload` | Đối chiếu đầy đủ với output snapshot |
| C07 `ket_qua_id` | `runtime.ket_qua_tieu_chi.ket_qua_id` | Quote/offsets ở `bang_chung_ket_qua`; chứng từ ở `bang_chung_ngoai` |
| C08 `tuan_thu_id` | `runtime.ket_qua_tuan_thu.tuan_thu_id` | Requirement instance + snapshot/counts; full coverage metadata trong DTO |
| C10 `ket_qua_rui_ro_id` | `runtime.ket_qua_rui_ro.ket_qua_id` | XOR `nguon_tieu_chi_id` / `nguon_vien_dan_id`; catalog `rui_ro_id` không phải instance |
| C11 `khuyen_nghi_ca_id` | `runtime.khuyen_nghi_danh_gia.khuyen_nghi_ca_id` | Bind `ket_qua_rui_ro_id`, không bind nhầm risk catalog |
| Knowledge bất biến | `knowledge.knowledge_snapshots`: `sha256`, `content` | Hash nội dung knowledge, không phải hash workbook/PDF |

`nguon_tieu_chi_id` là C07 `ket_qua_id`, không phải criterion catalog `tieu_chi_id`;
`nguon_vien_dan_id` là C09 `finding_id`, không phải C03 `vien_dan_id`. Quote offsets
là khoảng half-open `[start, end)` theo Unicode codepoints của chuỗi gốc trong
Python. Nhóm D không dùng chúng như byte offsets hoặc index UTF-16 của JavaScript,
và không normalize nội dung trước khi đối chiếu quote.

Writer lưu normalized rows, DTO, snapshots/pins và lineage trong một transaction.
Cùng input/case/run trả output cũ; input khác cùng run bị ConflictError. Output IDs
và nguồn đã dùng không được đổi nội dung. Rollback/concurrency và corruption được
kiểm chứng trên DB test riêng. Legacy snapshot thiếu membership không được nhận
ngầm là dữ liệu của run hiện tại.

## Chạy và kiểm chứng

[README Compliance](../backend/src/legal_checker/modules/compliance/README.md) có
provider/review/numeric contracts; [hướng dẫn PowerShell bàn giao](../outputs/group_c_completion_20261029_172537/powershell.md)
có offline/replay/save/read-run và các lệnh kiểm tra toàn repo.
Mỗi output directory phải mới. Runner mặc định không tạo paid provider; live API
chỉ thuộc runner C07 riêng khi được cho phép rõ ràng.

Gói bàn giao chứa input C02/C05/C06 có ghi nguồn, C07/C08/C10/C11 do engines thật tạo,
diagnostics, hashes, normalized rows, lineage, full-check logs/JUnit và metadata.
Demo có UNKNOWN phải giữ lý do thiếu xác minh; tests synthetic known findings không
được trình bày như nhãn chuyên gia của tài liệu thực.

## Giới hạn còn lại

OCR, Scope/Temporal, Retrieval/Citation upstream thật, UI, C12 human review và C13
publish/export không được nhóm C triển khai thay. Không có POST chạy riêng từng
bước 5–7 hoặc API khởi chạy assessment toàn bộ chỉ vì contracts đã tồn tại.
Knowledge flags draft/unverified và output PENDING vẫn giữ nguyên; snapshot không
đồng nghĩa đã được phê duyệt pháp lý. Authentication/tenant authorization của API
toàn hệ thống cần được chủ sở hữu phần đó triển khai.
