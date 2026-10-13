# Legal-Ai-Compliance-Checker

Backend Python/FastAPI cho AI Legal Compliance Checker theo BRD v1.1.
Development sử dụng **PostgreSQL local và dữ liệu workbook đã seed**.
Knowledge, runtime và snapshot lịch sử nằm trong DB; repo không chứa bộ DTO mẫu tĩnh.

- `backend/src/legal_checker/modules/`: nghiệp vụ và repository theo module.
- `shared/contracts/`: contracts C01–C13/X01/X02 và schemas bàn giao.
- `core/postgres.py`, `core/migrations.py`: connection và SQL migrations dùng chung.
- `api/dependencies.py`: tạo Knowledge PostgreSQL + Store PostgreSQL.
- `workflows/`: điều phối và kiểm tra các điểm bàn giao.

Bước 5–7 có engines deterministic: C05/C06 + observations → C07 → C08;
C07/C09 → C10; C10 + knowledge/templates → C11 chờ review.
Bước 1–4, review, export/UI và worker còn cần implementations thật;
không coi việc seed DB là bằng chứng OCR/search/LLM đã chạy.

## Bắt đầu

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e './backend[dev]' -c constraints.txt
cp .env.example .env
```

Nhận gói SYNTHETIC_DEV_VALIDATION của bộ v7.5.0 synthetic r2, giải nén vào
`data/private/v750_synthetic_r2/`
hoặc chỉnh `SEED_WORKBOOK_PATH` trong `.env`. Mỗi dev dùng DB riêng và cùng workbook.

```bash
docker compose up -d --wait postgres
python -m scripts.local_db init
python -m scripts.local_db seed
uvicorn legal_checker.main:create_app --factory --host 127.0.0.1 --port 8000
```

Máy không có Docker có thể dùng native server theo [hướng dẫn DB](docs/local_database.md).
Theo `.env.example`, DB ở `127.0.0.1:5433/legal_checker_dev_v750_synthetic_r2`;
Swagger: http://127.0.0.1:8000/docs.

```bash
python -m scripts.local_db check
python -m scripts.db_module_input --case CA90_001 --run CA90_001_SYN_R2_REFERENCE
curl -s http://127.0.0.1:8000/api/v1/knowledge
```

`db_module_input` in rows SQL thực để lập trình mapper/query độc lập.
Bản DEV_VALIDATION v7.5.0 có criterion IDs và C06 typed references trong schema QA;
Retrieval vẫn cần tìm/rank evidence thật và đánh giá relevance độc lập.
CLI cũng hỗ trợ workbook v7.4.9 và v7.5.0 SILVER gốc; các bản đó giữ nguyên hạn chế đã ghi nhận.

## API hiện có

| Endpoint | Chức năng |
|---|---|
| `POST /api/v1/reasoning` | C05/C06/chunks/observations → C07 |
| `POST /api/v1/aggregation` | C05 + C07 → C08 |
| `POST /api/v1/risks` | C05 + C07 + C09 → C10 |
| `POST /api/v1/recommendations` | C05 + C10 → C11 |
| `POST /api/v1/pipeline/steps-5-7` | Ghép bước 5–7, lưu kết quả vào PostgreSQL |
| `GET /api/v1/cases/{ca_id}/runs/{run_id}` | Đọc output bất biến của một lần chạy |
| `GET /api/v1/knowledge` | Hash/schema/counts của snapshot knowledge đang dùng |

Các endpoint độc lập là phép tính; endpoint pipeline mới ghi DB.
Input dùng contracts trong code và [OpenAPI](docs/openapi.json), cần đúng hash/case/run.
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
input khác trả 409. IDs/outputs đã dùng không được ghi đè bằng nội dung khác.
Nguồn chứng từ ngoài/mốc DI phải được đăng ký trước; pipeline không giả tạo PDF/LLM log.
API bước 5–7 hiện chưa phải hệ thống production authentication/tenant authorization.

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

Schemas có thể xuất mà không kết nối DB:

```bash
python -m scripts.export_openapi
python -m scripts.export_contracts
```

## Hướng dẫn nhóm

- [Triển khai theo nhóm bước 1–2, 3–4, 5–7 và 9](docs/huong_dan_trien_khai_module_sau_seed.md)
- [DB local, migration và seed](docs/local_database.md)
- [Bộ v7.5.0 dev/eval, gói dữ liệu và cách chạy](docs/v750_dev_eval.md)
- [Bộ v7.5.0 synthetic cho đồ án: 90 PDF và 15 nhóm tình huống](docs/v750_synthetic_eval.md)
- [Khởi tạo dependencies](docs/startup.md)
- [Ghép module](docs/module_integration.md)
- [Contracts nghiệp vụ](docs/data_contracts_v7_3_2.md), [schemas module](docs/module_contracts.schema.json)
- [Kiến trúc](docs/architecture.md), [chi tiết engines bước 5–7](docs/implementation.md)

Ruleset `main`: PR bắt buộc, 0 approval, CI thành công và up-to-date, resolve discussions,
chỉ squash, chặn xóa/force push, không bypass.
