# Kiến trúc backend theo module

Backend là modular monolith Python/FastAPI. Package `legal_checker` dùng src layout tại `backend/src/legal_checker/`; nghiệp vụ và repository được đặt cùng module theo cấu trúc người dùng chọn.

```text
backend/
├── src/
│   ├── legal_checker/
│   │   ├── main.py
│   │   ├── api/v1/                 # contracts, assessments, reviews, reports, legal_knowledge
│   │   ├── core/                   # config, postgres, security, logging, exceptions
│   │   ├── migrations/             # Alembic env, revisions, SQL baseline, legacy adoption
│   │   ├── shared/                 # contracts, llm audit, storage, ids, validation
│   │   ├── modules/
│   │   │   ├── documents/
│   │   │   ├── legal_knowledge/
│   │   │   ├── applicable_law/
│   │   │   ├── citation_validation/
│   │   │   ├── retrieval/
│   │   │   ├── compliance/
│   │   │   ├── risks/
│   │   │   ├── recommendations/
│   │   │   ├── assessments/
│   │   │   ├── reviews/
│   │   │   └── reports/
│   │   ├── workflows/              # assessment_workflow, steps_5_7, handoffs, states
│   │   └── worker/                 # celery_app, task chạy run và khôi phục run bị mất
│   └── devtools/                   # Tải dataset, seed SQL và kiểm tra QA
├── tests/{unit,integration,contract,e2e}/
├── alembic.ini
├── pyproject.toml
└── Dockerfile
```

[Backend README](../backend/README.md) mô tả trạng thái và trách nhiệm từng folder. `frontend`, `scripts`, `docs`, `data`, `configs` và `evals` vẫn ở root repo. Tài liệu BRD/contracts người dùng cung cấp được giữ làm baseline, kể cả các ví dụ cấu trúc cũ trong tài liệu gốc.

## Mapping BRD

| Bước / Chức năng | Module | Dữ liệu và trạng thái |
|---|---|---|
| 1–2 Document | `documents` | C01 → C02/C03/chunks; interfaces, chưa có parser/OCR thật |
| Knowledge | `legal_knowledge` | Repository PostgreSQL và immutable snapshots; curation/versioning là interface |
| 3A Scope/Temporal | `applicable_law` | C02 → C04 → C05; interfaces |
| 3B Citation | `citation_validation` | C03 + profile/knowledge → C09; interface độc lập |
| 4 Retrieval | `retrieval` | C05 + chunks → C06; interfaces |
| 5 Compliance | `compliance` | C05/C06/observations/knowledge → C07 → C08; chỉ còn skeleton |
| 6 Risk | `risks` | C07 + C09 → C10; hai mappers là skeleton |
| 7 Recommendation | `recommendations` | C10 + templates → C11; skeleton chờ triển khai |
| Assessment | `assessments` | Service đánh giá là skeleton; repository PostgreSQL giữ để đọc/lưu DTO |
| 8 Review | `reviews` | C12 service/repository interfaces, chưa triển khai |
| 9 Report | `reports` | Builder C13 ghép C10/C11 được cung cấp; chưa export/persist/publish |

## Dependency

- API dùng shared contracts và gọi module service/workflow; API không chứa rules pháp lý.
- Workflows chọn thứ tự gọi, truyền context/knowledge và kiểm tra bàn giao.
- Module sở hữu thuật toán, prompts, queries và repository của mình.
- `core/postgres.py` tạo connection chung; repository sở hữu SQL và transaction. Knowledge và assessment repositories đang dùng PostgreSQL.
- Module tự sở hữu LLM/embeddings, client/provider/prompt. `shared/llm/audit.py` cung cấp X02 sink/helper dùng chung. `shared/storage/http.py` triển khai đọc nguồn HTTP(S), kiểm tra SHA-256 và cache local cho nhóm A; [hướng dẫn](source_storage.md).
- Alembic quản lý schema qua `migrations/versions/`; ba revision đầu dùng SQL baseline trong `migrations/sql/`. `scripts.local_db init` chạy tới head và kiểm tra lịch sử/checksum/cấu trúc trước khi tiếp nhận DB dùng runner cũ. Xem [quy trình migration](database_migrations.md).
- Compliance/risk/recommendation hiện chỉ có chữ ký hàm và `NotImplementedError`. Người phụ trách tự triển khai logic và nối provider nếu cần.
- Contracts chỉ mô tả dữ liệu. Runtime không import `devtools`.
- `main.create_app` và `api.dependencies.build_services` chọn implementations; các Protocol được đặt cùng module sở hữu.

Luồng mục tiêu sau khi triển khai API assessment toàn bộ; hiện chưa có endpoint khởi chạy luồng này:

```mermaid
flowchart TD
    API[API] --> AS[Assessment service]
    AS --> W[Workflow]
    W --> C[Compliance: C07 và C08]
    C --> R[Risk: C10]
    CV[Citation: C09] --> R
    R --> N[Recommendation: C11]
    AS --> DB[Assessment repository]
    DB --> CONN[Core database]
    CONN --> SQL[PostgreSQL]
    K[Knowledge repository] --> W
```

Applicable Law chỉ nhận profile/scope/knowledge; Citation Validation nhận citations/profile/knowledge riêng. C09 hội tụ ở Risk/Report, không sửa C05 hoặc C08. C05 vẫn là context/checklist cho Retrieval và Compliance; C06 chỉ là evidence references.

`DraftAssessmentWorkflow` trong `workflows/assessment_workflow.py` giữ wiring upstream; hiện dừng với `NotImplementedError` ở bước 5 dù đã inject đủ upstream services. Nó giữ C01 pin, C04/C05/C06, C03/C09 và C07–C11 trong `AssessmentDraft`; chưa phải workflow đã triển khai đầy đủ bước 1–9. Fixtures upstream dùng để kiểm tra bàn giao, không chứng minh OCR/LLM/retrieval quality.

## Điểm đặt code và skeleton

| Chức năng trước | Nơi sở hữu hiện tại |
|---|---|
| Criterion reasoning + requirement aggregation | `modules/compliance/criterion_reasoner.py`, `requirement_aggregator.py` |
| Entry point Compliance | `modules/compliance/service.py:evaluate_compliance` |
| Risk branches | `modules/risks/compliance_mapper.py`, `citation_mapper.py`, `aggregator.py` |
| Recommendation | `modules/recommendations/generator.py`, `validator.py` |
| PostgreSQL knowledge reader | `modules/legal_knowledge/repository.py` |
| PostgreSQL run store | `modules/assessments/repository.py`, connection chung trong `core/postgres.py` |
| C13 draft | `modules/reports/builder.py` |
| Document/source/search interfaces | `modules/documents/parser.py`, `shared/storage/source.py`, `modules/retrieval/` |
| Khởi tạo dependency | `api/dependencies.py`, được gọi từ `main.py` |

Không giữ package `app`, `business_modules`, `adapters`, `workflows/interfaces` hay import aliases cho đường dẫn trước. Contracts API được giữ; knowledge/run persistence đã chuyển sang PostgreSQL. Các endpoint hiện có được giữ; routes reviews/reports/contracts mới chỉ có APIRouter rỗng.

Xem [khởi tạo](startup.md), [nối module](module_integration.md) và [hướng dẫn nhóm](huong_dan_trien_khai_module_sau_seed.md).

## Trạng thái skeleton bước 5–7

Implementation cũ của bước 5–7 đã được xóa theo yêu cầu. Folder và chữ ký entrypoint được giữ để nhóm C tự triển khai. Không còn numeric rules, criterion reasoning, requirement aggregation, risk mapping hoặc template generation đang chạy.

| Module | Input dự kiến | Output dự kiến | File triển khai |
|---|---|---|---|
| Compliance | C05 + C06 + chunks/facts/observations + knowledge đã pin | C07 rồi C08 | `criterion_reasoner.py`, `grounding_validator.py`, `requirement_aggregator.py`, `service.py` |
| Risks | C07/C08 + C09 + knowledge | C10, giữ provenance hai nhánh | `compliance_mapper.py`, `citation_mapper.py`, `aggregator.py`, `service.py` |
| Recommendations | C10 + C05/context + knowledge | C11 chờ review | `generator.py`, `validator.py`, `service.py` |

Các hàm trên và `workflows/steps_5_7.evaluate` phát sinh `NotImplementedError`. Các routes POST chạy riêng reasoning/aggregation/risks/recommendations/pipeline đã xóa. Contracts vẫn dùng để bàn giao giữa các hàm Python; API khởi chạy assessment toàn bộ đã có (`POST /api/v1/cases/{ca_id}/runs`, nhóm D); khi chưa có module bước 1–7, run kết thúc FAILED với `MODULE_NOT_IMPLEMENTED`. Xem [demo](demo.md).

Giữ nguyên contracts C01–C13, Knowledge PostgreSQL reader, Store, migrations, scripts tải dataset/seed và dữ liệu tham chiếu đã khóa phiên bản. GET knowledge/run vẫn dùng được. Dữ liệu EXPECTED trong QA là kết quả tham chiếu của phiên bản dựng dataset trước đây; không chứng minh module hiện tại đã triển khai hoặc đã pass eval.

`reports.build_draft_report` chỉ ghép dữ liệu được truyền vào. Caller phải cung cấp `risks=` và `recommendations=` là C10/C11 đã hợp nhất; builder không tự chạy bước 6–7.

Các CLI placeholder đánh giá và công cụ dựng lại release lịch sử đã xóa. Chưa có runner/evaluator CLI cho implementation mới; tải/seed bản frozen hiện tại vẫn hoạt động.

Người phụ trách triển khai query/mapper theo [hướng dẫn sau seed](huong_dan_trien_khai_module_sau_seed.md), nghiệp vụ theo BRD và contracts, sau đó bổ sung tests của module và bật lại wiring/API/CLI bằng kết quả thật.

## Audit LLM dùng chung

`Services.llm_audit` được factory khởi tạo bằng `PostgresLlmAuditSink`, ghi vào bảng `runtime.nhat_ky_goi_llm` có sẵn. Mỗi module inject sink khi khởi tạo service; audit không chọn provider hoặc tạo client. `audit_llm_call` chỉ giữ hashes/metadata, đo latency và ghi từng attempt; không ghi raw prompt, response hoặc API key. Usage/cost chưa biết giữ null. [Quy ước, ví dụ và xử lý lỗi](llm_audit.md).
