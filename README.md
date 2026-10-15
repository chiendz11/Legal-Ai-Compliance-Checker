# Legal-Ai-Compliance-Checker

Backend Python/FastAPI cho AI Legal Compliance Checker theo BRD v1.1.
Development sử dụng **PostgreSQL local và dữ liệu workbook đã seed**.
Knowledge, runtime và snapshot lịch sử nằm trong DB; repo không chứa bộ DTO mẫu tĩnh.

- `backend/src/legal_checker/modules/`: nghiệp vụ và repository theo module.
- `shared/contracts/`: contracts C01–C13/X01/X02 và schemas bàn giao.
- `core/postgres.py`: connection dùng chung; `migrations/`: quản lý schema bằng Alembic.
- `api/dependencies.py`: tạo Knowledge PostgreSQL + Store PostgreSQL.
- `workflows/`: điều phối và kiểm tra các điểm bàn giao.

Bước 5–7 hiện **chỉ còn skeleton**; các entrypoint phát sinh `NotImplementedError`.
Các route HTTP chạy riêng bước 5–7 đã bỏ. Nhóm C tự triển khai C07/C08/C10/C11;
contracts, DB, dữ liệu seed tham chiếu và chức năng đọc run vẫn được giữ.
Bước 1–4, review, export/UI và worker cũng cần implementations thật.

## Bắt đầu

[Hướng dẫn tạo môi trường ảo cho Linux/macOS/Windows](docs/dev_setup.md) có đầy đủ lệnh activate, cài dependencies, tải/seed và chạy API. [Danh sách scripts và trạng thái](scripts/README.md).

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e './backend[dev,dataset]' -c constraints.txt
cp .env.example .env
```

Tải gói DEV_VALIDATION bằng một lệnh; manifest trong repo pin link Drive, phiên bản
và SHA-256 của **v7.5.0-source-pdf360-r2-structured / supabase-public-v1**:

```bash
python -m scripts.dataset pull
python -m scripts.dataset check
```

Script tự tạo `data/private/v750_source_pdf360_r2_supabase/`, cài 335 file gồm workbook
đầy đủ và các references, bỏ qua nếu đã đúng bản và giữ nguyên folder hiện có
nếu phát hiện file khác hash. Gói chứa **240 DEV + 60 VALIDATION**; mỗi dev dùng DB
local riêng và cùng workbook. Script tải không tự seed hoặc thay đổi DB.

Drive yêu cầu đăng nhập hoặc hết quota: tải ZIP trong trình duyệt rồi dùng
`python -m scripts.dataset pull --archive /path/to/DEV_VALIDATION.zip`.
Xem [hướng dẫn tải dataset](docs/dataset_download.md).

Dataset nằm ngoài Git. `data/private/` và `.env` được bỏ qua bởi Git; thư mục private
cũng được loại khỏi Docker build context. Các workbook chia nhỏ chỉ dùng để xem,
seed DB vẫn dùng `bang_du_lieu_runtime_v7_5_0_360_STRUCTURED_R2_SUPABASE_DEV_VALIDATION.xlsx`.
PDF có URL public trong `tep_nguon.object_uri`; text/controlled references đọc từ
`sources/` của gói local. Xem [cách tổ chức data local](data/README.md).

```bash
docker compose up -d --wait postgres
python -m scripts.local_db init
python -m scripts.local_db seed
uvicorn legal_checker.main:create_app --factory --host 127.0.0.1 --port 8000
```

Máy không có Docker có thể dùng native server theo [hướng dẫn DB](docs/local_database.md).
Theo `.env.example`, DB ở `127.0.0.1:5433/legal_checker_dev_v750_r2_supabase`;
Swagger: http://127.0.0.1:8000/docs.

```bash
python -m scripts.local_db check
curl -s http://127.0.0.1:8000/api/v1/knowledge
```

Mỗi module tự viết query và mapper từ DB theo [hướng dẫn JOIN sau seed](docs/huong_dan_trien_khai_module_sau_seed.md).
Bản DEV_VALIDATION v7.5.0 có criterion IDs và C06 typed references trong schema QA;
Retrieval vẫn cần tìm/rank evidence thật và đánh giá relevance độc lập.

## API hiện có

| Endpoint | Chức năng |
|---|---|
| `GET /health` | Kiểm tra ứng dụng đang chạy |
| `GET /api/v1/cases/{ca_id}/runs/{run_id}` | Đọc output bất biến của một lần chạy |
| `GET /api/v1/knowledge` | Hash/schema/counts của snapshot knowledge đang dùng |

Các module bước 5–7 giao tiếp qua hàm Python/contracts nội bộ, không có POST riêng.
API bắt đầu đánh giá toàn bộ ca vẫn cần triển khai; GET run đọc dữ liệu đã lưu.
Input dùng contracts trong code và schema runtime tại `/openapi.json` khi chạy backend,
cần đúng hash/case/run.
Không có default payload dựa trên file mẫu cũ.

## Knowledge và persistence

`Knowledge` đọc 18 bảng knowledge nghiệp vụ, tạo snapshot nội dung có SHA256 trong
`knowledge.knowledge_snapshots`. Các bảng quản trị vẫn giữ riêng ở schema knowledge.
Snapshot giữ flags draft/unverified; mặc định `DEV_UNVERIFIED`, không tự duyệt tri thức.
`KNOWLEDGE_SNAPSHOT_SHA256` chọn snapshot lịch sử đã có trong DB. Không dùng hash Excel
làm hash knowledge. Muốn nạp thay đổi source tables vào app, khởi tạo lại reader/app.

`Store` ghi các bảng runtime workbook theo cột/quan hệ thật, đồng thời giữ input/output
trong `runtime.assessment_runs`, pins trong `assessment_case_pins`, và DTO/run lineage
trong `assessment_output_lineage`. Một transaction; cùng input/case/run trả output đã lưu,
input khác bị Store từ chối bằng ConflictError. IDs/outputs đã dùng không được ghi đè bằng nội dung khác.
Nguồn chứng từ ngoài/mốc DI phải được đăng ký trước; pipeline không giả tạo PDF/LLM log.
API bước 5–7 hiện chưa triển khai nghiệp vụ; authentication/tenant authorization cũng cần triển khai.

## Kiểm tra

```bash
ruff check --config backend/pyproject.toml .
ruff format --check --config backend/pyproject.toml .
TEST_DATABASE_URL='postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_test' \
  pytest -q -c backend/pyproject.toml
```

Tests tạo DB con riêng, nạp SQL seed nhỏ trong `backend/tests/seed_knowledge.sql`, rồi xóa
DB test. Các DTO test được dựng trong tests hoặc đọc từ DB test; không phụ thuộc file
Downloads hoặc cloud DB. Thiếu `TEST_DATABASE_URL` thì nhóm test cần DB được skip.
CI luôn có PostgreSQL service và check **CI / required**.

[Contracts máy đọc được](docs/contracts/README.md) có schema riêng C01–C13/X01/X02 và catalog module/DB.
[OpenAPI thiết kế UI](docs/openapi.design.json) phục vụ frontend mock và backend triển khai;
Backend đang chạy cung cấp `/openapi.json` để xem routes thực tế; không lưu thêm bản JSON runtime trong repo.
Các endpoints dự kiến trong bản thiết kế được đánh dấu rõ,
chưa tự hoạt động chỉ vì đã có đặc tả JSON.

Đặc tả JSON đã được xuất và giữ trong repo; công cụ sinh đã xóa. Khi đổi contract,
cập nhật JSON, model/backend và hướng dẫn liên quan trong cùng PR. Tests kiểm tra
tính hợp lệ và đối chiếu với models, không tự ghi đè đặc tả.

## Hướng dẫn nhóm

[Mục lục tài liệu](docs/README.md).

- [Triển khai theo nhóm bước 1–2, 3–4, 5–7 và 9](docs/huong_dan_trien_khai_module_sau_seed.md)
- [DB local, migration và seed](docs/local_database.md)
- [Alembic: cập nhật schema và tiếp nhận DB cũ](docs/database_migrations.md)
- [Bộ hiện tại: 360 PDF, structured r2](docs/v750_source_pdf360_r2_structured.md)
- [Audit LLM dùng chung, client riêng từng module](docs/llm_audit.md)
- [Khởi tạo dependencies](docs/startup.md)
- [Ghép module](docs/module_integration.md)
- [Contracts nghiệp vụ](docs/data_contracts_v7_3_2.md), [schemas module](docs/module_contracts.schema.json)
- [Kiến trúc](docs/architecture.md), [trạng thái skeleton bước 5–7](docs/architecture.md#trạng-thái-skeleton-bước-57)

Ruleset `main`: PR bắt buộc, 0 approval, CI thành công và up-to-date, resolve discussions,
chỉ squash, chặn xóa/force push, không bypass.
