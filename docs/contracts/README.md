# Contracts máy đọc được cho phát triển song song

Các JSON trong folder này là đặc tả dữ liệu để IDE, coding agent, validator và
code generator sử dụng. Không chứa đáp án dataset hoặc triển khai nghiệp vụ.
Nguồn nghiệp vụ là [BRD](../BRD_v1.1.pdf), [contracts gốc](../data_contracts_v7_3_2.md)
và [giải thích contracts](../contracts_va_muc_dich_vi.md).

## Chọn đúng file cho công việc

| File | Người dùng và công dụng |
|---|---|
| [OpenAPI thiết kế UI](../openapi.design.json) | Frontend mock/sinh client; backend triển khai request/response đã đề xuất |
| [catalog.json](catalog.json) | Tra ID contract → model, schema, producer/consumer, bảng lưu, cardinality và quy tắc nghiệp vụ |
| `C01.schema.json` … `C13.schema.json`, `X01.schema.json`, `X02.schema.json` | Validate cấu trúc **một record** của từng contract bằng JSON Schema 2020-12 |
| [Schemas handoff tổng hợp](../module_contracts.schema.json) | Input/output theo module, gồm context và các danh sách record |
| [database_catalog.json](database_catalog.json) | Tên/cột/kiểu SQL/PK của 50 bảng workbook + 6 bảng QA và 78 FK workbook |

Đặc tả JSON đã được xuất và hiện được quản lý trực tiếp trong repo; công cụ sinh đã xóa.
Giữ models trong `legal_checker/shared/contracts/` vì backend dùng để validate dữ liệu.
Khi đổi contract, cập nhật JSON và model tương ứng trong cùng PR để tránh lệch nhau.
Catalog không thay SQL migrations hoặc tự thực thi các quy tắc được ghi trong nó.

## Frontend và backend dùng OpenAPI thiết kế thế nào?

Schema runtime xem trực tiếp tại `http://127.0.0.1:8000/openapi.json` sau khi chạy backend;
Swagger ở `/docs`. Repo không lưu thêm một bản runtime JSON.

`openapi.design.json` là **PROPOSED**, gồm 20 operations: 3 GET đang có implementation
và 17 operations cần triển khai. Mỗi operation ghi `x-implementation-status`:

- `IMPLEMENTED`: có handler hiện tại; xem `/openapi.json` của backend để biết hành vi đang chạy.
- `NOT_IMPLEMENTED`: frontend dùng làm contract/mock; backend cần viết route/service/repository.

Đặc tả mới có request/response typed, `operationId` ổn định, phân trang, lỗi, nguồn
file binary/multipart, chống gửi nhầm dữ liệu server sở hữu và liên kết case/run/review/report.
Luồng chính:

```text
POST /contracts (multipart PDF/DOCX)
    → POST /cases (ID hợp đồng, mốc đánh giá)
    → POST /cases/{ca_id}/runs (Idempotency-Key)
    → GET  /cases/{ca_id}/runs/{run_id}/status
    → GET  /cases/{ca_id}/runs/{run_id}/results
    → POST/GET /cases/{ca_id}/runs/{run_id}/reviews
    → POST/GET /cases/{ca_id}/runs/{run_id}/reports
    → GET /reports/{bao_cao_id}
    → POST /reports/{bao_cao_id}/publish
    → GET /reports/{bao_cao_id}/export?format=pdf
```

Mọi đường dẫn trên có prefix `/api/v1`. Các GET danh sách contracts/cases và GET
nguồn hợp đồng cũng nằm trong spec. UI đọc nguồn PDF để mở đúng trang evidence.
COMPLETED là máy đã xử lý xong, không đồng nghĩa với báo cáo đã duyệt.

Endpoint `/pipeline/steps-5-7` và các POST module đã xóa khỏi code và schema runtime.
Các module bước 5–7 gọi qua hàm Python/contracts; API frontend dùng luồng assessment toàn bộ.
GET `/cases/{ca_id}/runs/{run_id}` cũ chỉ đọc output 5–7 đã lưu, không phải full report.

Các quy ước **thiết kế** cần backend thực thi khi triển khai:

- Tenant/actor lấy từ danh tính đã xác thực; client không được tự quyết định chúng.
- Backend pin deployment, knowledge hash, run/trace IDs; frontend không gửi C05/C06.
- Retry lệnh start dùng cùng `Idempotency-Key`; khóa mới để yêu cầu run mới.
- Pagination dùng `page` từ 1, `page_size` mặc định 20/tối đa 100; response có `total`.
- Lỗi mới có `{ "error": { "code", "message", "trace_id", "details" } }`.
  Backend cần exception handlers để áp dụng kể cả lỗi validation 422.
- Các GET cũ giữ lỗi FastAPI hiện tại; không được coi error envelope mới đã hoạt động.
- Review request gửi target/action/after/reason/hash kỳ vọng; server tạo actor,
  before state, review ID và thời gian. Phải kiểm tra target thuộc đúng case/run.
- Report version gắn đúng run và review revision. Publish từ chối revision cũ hoặc
  review bắt buộc chưa đủ; export draft phải hiển thị trạng thái nháp.
- Quy ước tiền Decimal: response có thể là chuỗi, không tự làm tròn bằng số thực JavaScript.
- `null`, UNKNOWN, INSUFFICIENT và sự khác nhau giữa citation/compliance phải hiển thị rõ.

Bearer authentication, writer, worker/progress, exception handlers, publish và export
ở các operation dự kiến **chưa được triển khai**. Workflow đăng nhập/quản lý quyền và
API curator duyệt/phát hành knowledge là thiết kế tiếp theo, chưa đặc tả chi tiết ở bản UI MVP này.
Chưa có code sinh client hoặc chọn framework frontend tự động.

Có thể import `openapi.design.json` vào công cụ đọc OpenAPI hoặc dùng nó làm input
cho generator của stack frontend đã chọn. Khi đổi thiết kế API, sửa trực tiếp JSON,
đối chiếu các bên sử dụng và kiểm tra hợp lệ trước khi commit.

## Người làm module dùng JSON Schema thế nào?

Ví dụ người làm Retrieval:

1. Đọc `catalog.json`: Retrieval nhận C05 + chunks + knowledge, trả danh sách C06.
2. Input đầy đủ theo `RetrievalInput` trong bundle handoff; knowledge là dependency riêng.
3. Mỗi record output theo `C06.schema.json`, giữ đúng IDs của case/run/criterion/chunk.
4. Repository/mapper tự đọc và chuyển dữ liệu DB; xem [recipe JOIN](../huong_dan_trien_khai_module_sau_seed.md).
5. Validate schema và các quy tắc nghiệp vụ trước khi lưu/bàn giao.

Ví dụ kiểm tra một record đã có trong Python, sau khi cài backend extra `[dev]`:

```python
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from legal_checker.shared.contracts.retrieval import RetrievalEvidence

schema = json.loads(Path("docs/contracts/C06.schema.json").read_text())
payload = my_retrieval_record  # Output thực tế do module của bạn tạo.
Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
record = RetrievalEvidence.model_validate(payload)
```

Schema riêng mô tả một record. Với contract có `handoff_cardinality: many`, validate
từng record hoặc dùng model input/output chứa list trong bundle handoff.
Pydantic vẫn bắt buộc ở backend: JSON Schema không biểu diễn hết `model_validator`
và không chứng minh quote thực sự nằm trong PDF hay target thuộc cùng case/run.

Catalog đánh dấu rõ các gap hiện tại để người dev xử lý có chủ đích:

- C03 chưa có offsets/bbox occurrence chi tiết trong DTO citation hiện tại.
- C12 chưa có run_id riêng trong DTO/bảng; writer phải pin và kiểm tra target membership.
- C13 version DTO là string, SQL là INTEGER; thống nhất mapper/migration trước khi ghi.
- C11 metadata hiện là template engine; muốn dùng LLM cần thay contract có review.

`database_catalog.json` là danh mục cột/khóa, không phải migration hoặc schema đầy đủ
về defaults/nullability/checks. Bốn bảng snapshot/run bổ sung nằm trong migration 002;
catalog ghi đường dẫn migrations và bảng lineage. SQL đã áp dụng không được sửa để khớp
file tài liệu. Không tạo bảng mới chỉ vì có một contract mới.

## Cập nhật và kiểm tra

Các file cần sửa tùy phần thay đổi:

| Thay đổi | Nguồn |
|---|---|
| Fields/enum module | `backend/src/legal_checker/shared/contracts/`, schema record tương ứng và bundle handoff/X02 nếu liên quan |
| HTTP UI dự kiến, body/response và mô tả | `docs/openapi.design.json` |
| Producer/consumer, quy tắc, mapping bảng | `docs/contracts/catalog.json` |
| HTTP đang chạy | `backend/src/legal_checker/api/`; xem schema runtime tại `/openapi.json` |
| Cấu trúc DB mới | Thêm SQL migration, cập nhật metadata DB và `docs/contracts/database_catalog.json` tương ứng |

Từ root repo:

```bash
pytest -q -c backend/pyproject.toml backend/tests/contract/test_machine_contracts.py
```

Test đọc các file JSON, kiểm tra khớp models, OpenAPI hợp lệ, JSON Schema/refs, ví dụ HTTP, mapping
bảng và nhãn implementation. CI hiện chạy bộ test này cùng các tests còn lại; không cần
DB để kiểm tra riêng các file contract; tests không sinh hoặc ghi lại đặc tả. Khi implement API mới, cập nhật nhãn
và đối chiếu runtime với design trong cùng PR; không chỉ đổi nhãn để báo đã hoàn thành.

Chuẩn định dạng: [OpenAPI 3.1](https://spec.openapis.org/oas/v3.1.0.html) và
[JSON Schema 2020-12](https://json-schema.org/draft/2020-12).
