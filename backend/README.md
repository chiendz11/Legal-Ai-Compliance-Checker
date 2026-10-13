# Backend theo module

Package Python là `legal_checker`, nằm tại `backend/src/legal_checker/`. Mỗi module giữ logic, repository và interfaces của mình. `core` cung cấp cấu hình/kết nối chung; `shared` cung cấp contracts và các công cụ được nhiều module sử dụng.

## Các phần chính

| Folder | Trách nhiệm | Hiện trạng |
|---|---|---|
| `api/v1` | Nhận HTTP, parse contracts, gọi service/workflow, ánh xạ lỗi | API bước 5–7, GET snapshot/knowledge và health đang chạy; routes contracts/reviews/reports chưa có endpoints |
| `core` | Settings, tạo kết nối PostgreSQL và SQL migrations, lỗi, security/logging chung | Config/database/exceptions đang chạy; security là interface; logging chưa triển khai |
| `shared/contracts` | Schemas C01–C13/X01/X02 và input/output bàn giao | Đang dùng trong API, modules và tests |
| `shared/llm`, `shared/embeddings` | Kết nối provider dùng chung; module tự sở hữu prompt và cách dùng | Chưa có provider |
| `shared/storage` | Khả năng đọc bytes tài liệu nguồn | Interface `SourceStorage`, chưa có object-storage implementation |
| `modules/documents` | Intake, parser/OCR, chia đoạn, trích profile/viện dẫn, lưu metadata | Interfaces; parser/OCR/extraction thật chưa triển khai |
| `modules/legal_knowledge` | Đọc/quản lý knowledge và phiên bản | Repository SQL + immutable snapshots đang chạy |
| `modules/applicable_law` | Scope, checklist, phiên bản pháp luật áp dụng | Interfaces và skeleton |
| `modules/citation_validation` | Chuẩn hóa, xác thực và phân loại viện dẫn C09 | Interfaces và skeleton |
| `modules/retrieval` | Index, tìm evidence, rerank và tạo C06 | Interfaces và skeleton |
| `modules/compliance` | Đánh giá criterion C07, tổng hợp C08, kiểm tra provenance | Engines deterministic đang chạy; chưa nối LLM |
| `modules/risks` | Map hai nguồn compliance/citation rồi tổng hợp C10 | Service, mappers và aggregator đang chạy |
| `modules/recommendations` | Chọn template C11 và kiểm tra C10 | Service, generator/validator đang chạy |
| `modules/assessments` | Gọi workflow, lưu/đọc run, checksum audit | PostgreSQL repository/service/audit + normalized runtime tables đang chạy |
| `modules/reviews` | Human review C12 và lưu events | Interfaces |
| `modules/reports` | Dựng report, lưu phiên bản và export | Builder C13 DRAFT/PENDING đang chạy; service/repository/exporter là interfaces |
| `workflows` | Điều phối module, kiểm tra bàn giao | Steps 5–7 đang chạy; draft workflow chạy khi inject đủ upstream services; states chưa triển khai |
| `worker` | Chạy services/workflow trong background | Chưa cấu hình Celery/broker hoặc đăng ký tasks |
| `alembic/versions` | Vị trí migrations DB | Chưa cấu hình Alembic; SQL migrations nằm tại core/sql |
| `tests` | Unit, integration, contract, E2E | Regression suite trên PostgreSQL test riêng |
| `src/devtools` | Excel seed/migration tooling | Development helpers; runtime không import package này |

Các file chỉ có docstring mô tả trách nhiệm là vị trí chờ triển khai, không tự trả kết quả thành công. Một số helpers bổ sung như `numeric_rules.py`, `interfaces.py`, `audit.py` giữ chức năng đã có.

## Cài và chạy

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
Docker build dùng root context; truyền DATABASE_URL tới PostgreSQL có thể truy cập
bên trong container, không dùng loopback host làm địa chỉ DB của container.

## Dependency và khởi tạo

`main.create_app()` gọi `api.dependencies.build_services()`. Hàm này đọc knowledge PostgreSQL qua `modules/legal_knowledge/repository.py` và khởi tạo run store qua `modules/assessments/repository.py`.

```text
HTTP → api/v1/assessments.py
     → modules/assessments/service.py
     → workflows/steps_5_7.py
     → modules/compliance, risks, recommendations
     → modules/assessments/repository.py
     → core/postgres.py → PostgreSQL
```

Module sở hữu queries và transactions trong repository; `core/postgres.py` dùng chung việc tạo connection. Các hàm đánh giá thuần nhận knowledge/evidence qua tham số. Khi nối provider, service của module có thể dùng client chung trong `shared/llm`; prompts và nghiệp vụ vẫn thuộc module đó.

Các interfaces đã chuyển tới nơi sử dụng: `KnowledgeSnapshot` ở `modules/legal_knowledge/models.py`, `AssessmentStore` ở `modules/assessments/interfaces.py`, reader ở `modules/documents/parser.py`, storage ở `shared/storage/source.py`, authorization ở `core/security.py`. Không còn package `app` hoặc lớp import chuyển tiếp.

Xem [khởi tạo](../docs/startup.md), [nối modules](../docs/module_integration.md) và [hướng dẫn nhóm](../docs/huong_dan_trien_khai_module_sau_seed.md).
