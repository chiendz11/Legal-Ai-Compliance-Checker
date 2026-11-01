# Backend theo module

Package Python là `legal_checker`, nằm tại `backend/src/legal_checker/`. Mỗi module giữ logic, repository và interfaces của mình. `core` cung cấp cấu hình/kết nối chung; `shared` cung cấp contracts và các công cụ được nhiều module sử dụng.

## Các phần chính

| Folder | Trách nhiệm | Hiện trạng |
|---|---|---|
| `api/v1` | Nhận HTTP, parse contracts, gọi service/workflow, ánh xạ lỗi | GET run/knowledge và health đang chạy; route POST nội bộ bước 5–7 đã bỏ; contracts/reviews/reports chưa có endpoints |
| `core` | Settings, tạo kết nối PostgreSQL, lỗi, security/logging chung | Config/database/exceptions đang chạy; security là interface; logging chưa triển khai |
| `shared/contracts` | Schemas C01–C13/X01/X02 và input/output bàn giao | Đang dùng trong API, modules và tests |
| `shared/llm` | Audit X02, types/config và transport client dùng chung | PostgreSQL audit sink và client OpenAI tùy chọn; module sở hữu prompt/schema/provider; runner nhóm C không tạo paid client |
| `shared/storage` | Đọc bytes tài liệu nguồn | `CachedHttpSourceStorage`: HTTP(S), SHA-256 và cache local; [cách dùng cho nhóm A](../docs/source_storage.md) |
| `modules/documents` | Intake, parser/OCR, chia đoạn, trích profile/viện dẫn, lưu metadata | Interfaces; parser/OCR/extraction thật chưa triển khai |
| `modules/legal_knowledge` | Đọc/quản lý knowledge và phiên bản | Repository SQL + immutable snapshots đang chạy |
| `modules/applicable_law` | Scope, checklist, phiên bản pháp luật áp dụng | Interfaces và skeleton |
| `modules/citation_validation` | Chuẩn hóa, xác thực và phân loại viện dẫn C09 | Interfaces và skeleton |
| `modules/retrieval` | Index, tìm evidence, rerank và tạo C06 | Interfaces và skeleton |
| `modules/compliance` | Đánh giá criterion C07, tổng hợp C08, kiểm tra provenance | Provider/review độc lập, bốn findings, 7 loại criterion, 12 numeric schema và AGG_CAN_HO_V1; service compliance-only đã triển khai |
| `modules/risks` | Map hai nguồn compliance/citation rồi tổng hợp C10 | Rules/catalog đã pin, guards, source XOR, severity và dedup giữ provenance; UNKNOWN chỉ verification theo policy |
| `modules/recommendations` | Chọn template C11 và kiểm tra C10 | Generator/validator/service dùng template, selection policy ALL, facts/limits và diagnostics; luôn PENDING |
| `modules/assessments` | Lưu/đọc run, checksum audit và runner nhóm C | PostgreSQL transaction giữ normalized rows/full DTO/pins/lineage; CLI offline/replay/save/read/export; service/API full assessment còn interface |
| `modules/reviews` | Human review C12 và lưu events | Interfaces |
| `modules/reports` | Dựng report, lưu phiên bản và export | Builder C13 nhận C10/C11 đã cung cấp, không tính risk/actions; service/repository/exporter là interfaces |
| `workflows` | Điều phối module, kiểm tra bàn giao | Steps 5–7 đã chạy; DraftAssessmentWorkflow ghép upstream được inject; thiếu retrieval/observations/citation giữ diagnostics; states còn interface |
| `worker` | Chạy services/workflow trong background | Chưa cấu hình Celery/broker hoặc đăng ký tasks |
| `migrations` | Alembic revisions, SQL baseline và kiểm tra tiếp nhận DB cũ | `scripts.local_db init` chạy Alembic tới head; cấu hình tại `backend/alembic.ini` |
| `tests` | Unit, integration, contract, E2E | Regression suite trên PostgreSQL test riêng |
| `src/devtools` | Tải dataset, đọc/validate và seed Excel | Development helpers; runtime không import package này |

Các file chỉ có docstring mô tả trách nhiệm ở phần upstream/review/report/worker còn là
vị trí chờ triển khai, không tự trả kết quả thành công. Không suy từ trạng thái này sang
các engines C07/C08/C10/C11 đã triển khai. [Bàn giao nhóm C](../docs/group_c_handoff.md)
ghi luồng dữ liệu, mapping DB, bằng chứng checks và các phụ thuộc còn lại.

## Cài và chạy

[Hướng dẫn tạo/kích hoạt môi trường ảo](../docs/dev_setup.md) trình bày lệnh cho Linux/macOS và Windows, cùng setup dataset/DB.

Từ root repo:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e './backend[dev]' -c constraints.txt
uvicorn legal_checker.main:create_app --factory --host 127.0.0.1 --port 8000
pytest -q -c backend/pyproject.toml
```

Từ folder `backend`, sau khi activate môi trường:

```bash
pip install -e '.[dev]' -c ../constraints.txt
uvicorn legal_checker.main:create_app --factory
pytest -q
```

Cấu hình bằng `DATABASE_URL` và optional `KNOWLEDGE_SNAPSHOT_SHA256`.
Workbook gốc và DB native nằm trong `data/private/`, được Git bỏ qua.
Dựng DB/seed theo [hướng dẫn local](../docs/local_database.md) trước khi chạy API.
Khi thay đổi bảng/cột, thêm revision theo [hướng dẫn Alembic](../docs/database_migrations.md); seed workbook vẫn là bước riêng.
Docker build dùng root context; truyền DATABASE_URL tới PostgreSQL có thể truy cập
bên trong container, không dùng loopback host làm địa chỉ DB của container.

## Dependency và khởi tạo

`main.create_app()` gọi `api.dependencies.build_services()`. Hàm này đọc knowledge PostgreSQL qua `modules/legal_knowledge/repository.py` và khởi tạo run store qua `modules/assessments/repository.py`.

```text
GET run → assessments repository → core/postgres.py → PostgreSQL
GET knowledge → legal_knowledge repository → core/postgres.py → PostgreSQL
```

Module sở hữu queries và transactions trong repository; `core/postgres.py` dùng chung việc tạo connection. Các hàm đánh giá thuần nhận knowledge/evidence qua tham số. Module tự cấu hình LLM/embeddings, client/provider/prompt; dùng audit sink trong `shared/llm/audit.py` để ghi X02 theo cùng quy ước. Xem [audit LLM](../docs/llm_audit.md).

`compliance.service.evaluate_compliance` chỉ tạo C10/C11 từ nguồn compliance.
`workflows.steps_5_7.evaluate` nhận thêm C09 để hợp nhất cả hai nhánh. Không có default
OCR/Scope/Temporal/Retrieval/Citation hoặc review giả. Runner
`python -m legal_checker.modules.assessments.run_group_c` hỗ trợ offline, replay,
`--save`, `--read-run` và export; mặc định không gọi API trả phí.
Xem [các lệnh PowerShell](src/legal_checker/modules/compliance/README.md#runner-nhóm-c-bước-57).

`Store.get`, `get_input`, `get_lineage` đọc đúng case/run đã lưu, kiểm tra checksum,
pins, knowledge snapshot và normalized rows/lineage trong transaction đọc nhất quán;
không chạy reasoning/risk/recommendation. Report/nhóm D cần dùng các outputs này,
giữ diagnostics, UNKNOWN/INSUFFICIENT và trạng thái DRAFT/PENDING.

Các interfaces đã chuyển tới nơi sử dụng: `KnowledgeSnapshot` ở `modules/legal_knowledge/models.py`, `AssessmentStore` ở `modules/assessments/interfaces.py`, reader ở `modules/documents/parser.py`, storage ở `shared/storage/source.py`, authorization ở `core/security.py`. Không còn package `app` hoặc lớp import chuyển tiếp.

Xem [khởi tạo](../docs/startup.md), [nối modules](../docs/module_integration.md) và [hướng dẫn nhóm](../docs/huong_dan_trien_khai_module_sau_seed.md).
