# Legal-Ai-Compliance-Checker

Backend Python/FastAPI triển khai **bước 5–7 của mục 6 (Quy trình nghiệp vụ mục tiêu)** trong BRD v1.1:

1. **Compliance Reasoning + Rule Aggregation:** C05/C06 và observation có evidence → C07 → C08.
2. **Risk Aggregation:** C07 + C09 → C10; giữ nguồn `COMPLIANCE`, `CITATION`, `VERIFICATION` riêng.
3. **Recommendation / Remediation:** C10 + knowledge + context → C11; mọi kết quả chờ human review.

Baseline: [BRD v1.1](docs/BRD_v1.1.pdf), [contracts v7.3.2](docs/data_contracts_v7_3_2.md), workbook runtime người dùng cung cấp. Nhánh phát triển: `feat/brd-steps-5-7`.

## Chạy local

Python 3.11+; CI dùng Python 3.12. Chạy từ thư mục repo:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]' -c constraints.txt
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Swagger: http://127.0.0.1:8000/docs. SQLite mặc định: `data/private/runtime.sqlite3`; cấu hình bằng biến môi trường `DATABASE_PATH`.

```bash
curl -s http://127.0.0.1:8000/api/v1/knowledge
curl -s -X POST http://127.0.0.1:8000/api/v1/pipeline/steps-5-7 \
  -H 'Content-Type: application/json' --data-binary @examples/steps_5_7.json
```

[Payload ví dụ](examples/steps_5_7.json) là fixture tổng hợp minh họa một requirement thiếu nội dung, có nhãn fixture trong context; không phải đánh giá hợp đồng thực.

## API và ghép module

| Endpoint | Input | Output |
|---|---|---|
| `POST /api/v1/reasoning` | `Steps57Input`: C05, C06, chunks, observations | `CriterionReasoning` / C07 |
| `POST /api/v1/aggregation` | `RequirementAggregationInput`: C05 + C07 | `RequirementAggregation` / C08 |
| `POST /api/v1/risks` | `RiskInput`: C05 + C07 + C09 | `RiskResult` / C10 |
| `POST /api/v1/recommendations` | `RecommendationInput`: C05 + C10 | `Recommendation` / C11 |
| `POST /api/v1/pipeline/steps-5-7` | `Steps57Input` | `Steps57Result`; persist toàn bộ output |
| `GET /api/v1/cases/{ca_id}/runs/{run_id}` | case/run ID | Kết quả snapshot đã lưu |
| `GET /api/v1/knowledge` | — | Checksum, version, số record |

Envelope có `ca_id`, `phien_ban_id`, `rule_version`, `legal_knowledge_version`, `knowledge_snapshot_sha256`, `run_id`, `trace_id`, `contract_version`. Output có thêm `contract_name`, `produced_at`, `payload`. Consumer module nhận trực tiếp output predecessor; không cần chạy lại retrieval/reasoning. API independent là phép tính thuần; endpoint pipeline mới ghi DB.

Schema input/output được khai báo trong [`app/contracts/`](app/contracts/); OpenAPI sinh tự động. Xem [hướng dẫn tích hợp](docs/implementation.md) về trường dữ liệu, ownership, evidence và persistence.

## Quy tắc đã triển khai

- Retrieval rỗng không tạo `VIOLATED`; `MISSING` chỉ có khi nội dung bắt buộc, absence/coverage được xác minh, toàn bộ trang/phụ lục đọc được, nguồn/scope/version/ngoại lệ xác nhận và không mâu thuẫn.
- Evidence phải nằm trong selected FINAL retrieval, cùng hợp đồng, có quote khớp chính xác offset. Evidence ngoài phải được xác minh.
- Thiếu observation, dữ kiện, source, scope, version hoặc ngoại lệ → `UNKNOWN`; giữ requirement chưa resolve ở `INSUFFICIENT`.
- Theo `AGG_CAN_HO_V1`: scope/version chưa rõ → `INSUFFICIENT`; có vi phạm chứng minh → `NON_COMPLIANT` kèm coverage flag; còn `UNKNOWN` → `INSUFFICIENT`; tất cả `MISSING` đã xác minh → `NON_COMPLIANT`; đáp ứng một phần + thiếu đã xác minh → `PARTIAL`; tất cả đáp ứng → `COMPLIANT`.
- Citation VALID ở relevant date không thành STALE vì current status REPEALED. Citation chưa xác minh → verification risk. Citation không sửa checklist hoặc compliance status.
- Risk và recommendation tra rule/catalog/link trong workbook, theo đúng criterion/citation và snapshot. Severity giữ nguyên từ Risk Engine; `SATISFIED`/`VALID` không sinh hành động khắc phục.
- Rule số liệu dùng `Decimal`: thanh toán đầu gồm cọc và không tính hai lần, ngưỡng trước bàn giao theo loại bên bán, trước cấp giấy, kinh phí bảo trì, thời hạn bảo hành, hạn nộp hồ sơ và các tiêu chí đặt cọc. Các ngưỡng được đọc từ workbook đã cung cấp; code không tự cập nhật tri thức pháp luật.

## Knowledge và phạm vi tích hợp

`data/knowledge.json` chứa 12 bảng knowledge được nhập từ workbook: 356 criterion, 1.424 decision rule, 850 risk rule, cùng legal sources, versions, templates và exceptions. Giữ nguyên `human_verified`, trạng thái chờ review và giới hạn sinh nội dung.

```bash
python scripts/import_workbook.py '/path/to/runtime.xlsx' --output data/knowledge.json
```

Workbook gốc, hồ sơ/chunks hợp đồng và runtime demo không được nhập vào snapshot public. Chúng là input của các module trước hoặc fixture riêng. Snapshot có checksum workbook nguồn và API yêu cầu checksum knowledge khớp chính xác.

Engine bước 5 nhận **structured observations từ adapter rule/LLM hoặc reviewer**. Code tự tính các numeric rule được hỗ trợ; với các tiêu chí ngữ nghĩa khác, adapter cung cấp proposed finding và evidence, engine kiểm tra gates rồi mới phát hành C07. Chưa tích hợp nhà cung cấp LLM, OCR, scope/temporal/retrieval bước 1–4, human review bước 8 hay report bước 9. Không giả tạo log gọi LLM. Knowledge chưa human-approved vẫn giữ kết quả dạng `PENDING`; bộ khung này chưa cung cấp authentication, tenant authorization hay publish report.

SQLite là adapter MVP lưu JSON snapshots trong các bảng runtime, không phải migration hoàn chỉnh cho mọi cột của workbook. Case pin bất biến, run idempotent, ghi output/evidence/audit trong một transaction; đổi input cùng run hoặc đổi deployment của case trả `409`.

## Kiểm tra

```bash
ruff check .
ruff format --check .
pytest -q
```

CI chạy cùng lệnh trên PR và `main`, với check name **`CI / required`**. Ruleset active áp dụng `refs/heads/main`: PR bắt buộc, **0 approval**, CI thành công và up-to-date theo main, resolve review discussions, chỉ squash, cấm xóa/force push, không bypass actor.
