# Legal-Ai-Compliance-Checker

Backend Python/FastAPI cho AI Legal Compliance Checker theo BRD v1.1.
Development sử dụng **PostgreSQL local và dữ liệu workbook đã seed**.
Knowledge, runtime và snapshot lịch sử nằm trong DB; repo không chứa bộ DTO mẫu tĩnh.

- `backend/src/legal_checker/modules/`: nghiệp vụ và repository theo module.
- `shared/contracts/`: contracts C01–C13/X01/X02 và schemas bàn giao.
- `core/postgres.py`: connection dùng chung; `migrations/`: quản lý schema bằng Alembic.
- `api/dependencies.py`: tạo Knowledge PostgreSQL + Store PostgreSQL.
- `workflows/`: điều phối và kiểm tra các điểm bàn giao.

Luồng C07 có provider tạo Observation cho checklist, client OpenAI tùy chọn, bốn findings,
grounding và 8 numeric kinds (10 shapes gồm legacy) có allowlist. Runner mặc định offline, không phát sinh phí API;
xem [cách chạy và giới hạn](backend/src/legal_checker/modules/compliance/README.md).
C07 → C08 → C10 → C11 đã có engines thuần, workflow/DI và runner offline/replay.
C10 giữ hai nhánh compliance/citation độc lập; C11 dùng template đã pin và luôn chờ review.
Runner hỗ trợ save/read/export với PostgreSQL, kiểm tra đúng case/run, snapshots,
normalized rows và lineage. `--read-run` đọc output đã lưu, không chạy lại engines.
Xem [bàn giao nhóm C](docs/group_c_handoff.md) và [hướng dẫn chạy](backend/src/legal_checker/modules/compliance/README.md#runner-nhóm-c-bước-57).
Các route HTTP chạy riêng bước 5–7 đã bỏ. Bước 1–9, UI, review/report và worker đã có implementation với giới hạn còn cần nghiệm thu. Đọc [INTEGRATION_V1](docs/contracts/integration_spec.md) và [changelog tích hợp](docs/guides/integration_alignment_changes_20261105.md) trước khi ghép module.

## Bắt đầu

[Hướng dẫn tạo môi trường ảo cho Linux/macOS/Windows](docs/guides/dev_setup.md) có đầy đủ lệnh activate, cài dependencies, tải/seed và chạy API. [Danh sách scripts và trạng thái](scripts/README.md).

[Sổ tay triển khai song song](docs/guides/parallel_development_playbook.md) chốt các quy ước và acceptance.

[Bàn giao main và việc tiếp theo cho 5 người](docs/guides/team_onboarding_and_next_steps.md) hướng dẫn đồng bộ code/dataset/DB và các điểm tích hợp cần hoàn thiện.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e './backend[dev,dataset]' -c constraints.txt
cp .env.example .env
```

Baseline hiện hành là **PDF360_V4R2_20261110**: knowledge, runtime và QA cùng
snapshot HUMAN_VERIFIED theo quyết định chủ dự án. Gói có PDF v4 r2 và reference runtime dựng lại; xem [phạm vi gold/reference và cách cài](docs/guides/dataset_pdf360_v4r2_runtime_20261110.md).

Đáp án đã đối chiếu riêng được mô tả tại [Gold Answer Set và coverage](docs/guides/gold_answer_set_20261110.md).
Đợt [biên soạn Gold trực tiếp bằng suy luận AI](docs/guides/gold_direct_curation_20261110.md)
bổ sung các target pháp lý, identity và evidence có phạm vi. Full Gold toàn pipeline
vẫn chưa hoàn tất; chưa dùng để công bố accuracy end-to-end cho toàn hệ thống.
Trong lúc manifest còn `LOCAL_ARCHIVE_READY`, cài ZIP đã được bàn giao:

```bash
python -m scripts.dataset pull --archive /path/to/legal_compliance_v750_PDF360_V4R2_20261110_DEV_VALIDATION.zip
python -m scripts.dataset check
python -m scripts.dataset cache-sources
```

Script tự tạo `data/private/v750_pdf360_v4r2_runtime_20261110/`, cài các file được pin trong manifest gồm workbook
đầy đủ và các references, bỏ qua nếu đã đúng bản và giữ nguyên folder hiện có
nếu phát hiện file khác hash. Gói chứa **240 DEV + 60 VALIDATION**; mỗi dev dùng DB
local riêng và cùng workbook. Script tải không tự seed hoặc thay đổi DB.

Drive yêu cầu đăng nhập hoặc hết quota: tải ZIP trong trình duyệt rồi dùng
`python -m scripts.dataset pull --archive /path/to/DEV_VALIDATION.zip`.
Xem [hướng dẫn baseline mới](docs/guides/dataset_pdf360_v4r2_runtime_20261110.md).
Release này dùng DB mới; giữ DB cũ và lịch sử, không chạy reviewed-flags update.

Dataset nằm ngoài Git. `data/private/` và `.env` được bỏ qua bởi Git; thư mục private
cũng được loại khỏi Docker build context. Các workbook chia nhỏ chỉ dùng để xem,
seed DB dùng `bang_du_lieu_v7_5_0_PDF360_V4R2_20261110_DEV_VALIDATION.xlsx`.
PDF v4 r2 nằm trong ZIP; `tep_nguon.object_uri` dùng dataset URI. Chạy
`cache-sources` trước khi đọc PDF bằng shared storage. Controlled references đọc từ `sources/`. Xem [cách tổ chức data local](data/README.md).

```bash
docker compose up -d --wait postgres
python -m scripts.local_db init
python -m scripts.local_db seed
uvicorn legal_checker.main:create_app --factory --host 127.0.0.1 --port 8000
```

Máy không có Docker có thể dùng native server theo [hướng dẫn DB](docs/database/local_setup.md).
Theo `.env.example`, DB ở `127.0.0.1:5433/legal_checker_dev_team_20261107`;
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
| `GET /api/v1/cases`, `GET /api/v1/cases/{ca_id}` | Danh sách/chi tiết ca (C01) và run gần nhất |
| `POST /api/v1/cases/{ca_id}/runs` | Xếp hàng một lần đánh giá toàn bộ (header `Idempotency-Key`) |
| `GET …/runs/{run_id}/status`, `GET …/runs/{run_id}/results` | Tiến độ theo stage; draft bước 1–7 đã pin |
| `GET`/`POST …/runs/{run_id}/reports` | Phiên bản C13 của run; POST dựng lại draft (cùng nội dung → cùng phiên bản) |
| `GET /api/v1/reports/{bao_cao_id}`, `GET …/export?format=pdf\|docx` | Đọc/xuất đúng một phiên bản báo cáo |

Các module bước 5–7 giao tiếp qua hàm Python/contracts nội bộ, không có POST riêng.
Run đi qua `workflows/runner.py` → `DraftAssessmentWorkflow` → `build_draft_report`, chạy trong
API (`ASSESSMENT_QUEUE=inline`) hoặc Celery worker (`celery`). Khi chưa có module bước 1–7,
run kết thúc FAILED với lý do `MODULE_NOT_IMPLEMENTED`; `ASSESSMENT_MODULES=reference` phát lại
tham chiếu QA để kiểm thử tích hợp và báo cáo được gắn nhãn `REFERENCE_REPLAY`.
Đăng nhập bật bằng `AUTH_MODE=on` (tài khoản local qua `scripts.users`, cookie phiên có ký; route kiểm tra vai trò và chỉ đọc dữ liệu cùng tenant). `AUTH_MODE=off` dùng một danh tính dev cố định, chỉ cho môi trường local. `modules` xử lý bytes thật; `modules_di_reference`/`reference` chỉ dành DEV/EVAL.
[Kịch bản demo](docs/guides/demo.md).
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
Nghiệp vụ bước 5–7 được gọi qua hàm Python hoặc runner; API khởi chạy assessment toàn bộ
và authentication/tenant authorization vẫn cần triển khai.

Store đọc đúng cặp case/run trong snapshot lịch sử và kiểm tra cả DTO checksum, case pin,
knowledge đã pin, normalized rows và output lineage. Dữ liệu legacy thiếu provenance hoặc
lineage không được ghép bằng “run mới nhất” hay thay bằng QA EXPECTED. Nhóm D đọc các
outputs này để dựng báo cáo; không chạy lại reasoning/risk/recommendation.

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
[OpenAPI thiết kế UI](docs/architecture/openapi.design.json) phục vụ frontend mock và backend triển khai;
Backend đang chạy cung cấp `/openapi.json` để xem routes thực tế; không lưu thêm bản JSON runtime trong repo.
Bản thiết kế hiện khớp 26 method/path đã có handler; metadata và semantic policy được quản lý cùng INTEGRATION_V1. Schema hợp lệ không tự chứng minh quality hoặc release readiness.

Đặc tả JSON đã được xuất và giữ trong repo; công cụ sinh đã xóa. Khi đổi contract,
cập nhật JSON, model/backend và hướng dẫn liên quan trong cùng PR. Tests kiểm tra
tính hợp lệ và đối chiếu với models, không tự ghi đè đặc tả.

## Hướng dẫn nhóm

[Mục lục tài liệu](docs/README.md).

- [Triển khai theo nhóm bước 1–2, 3–4, 5–7 và 9](docs/huong_dan_trien_khai_module_sau_seed.md)
- [DB local, migration và seed](docs/database/local_setup.md)
- [Alembic: cập nhật schema và tiếp nhận DB cũ](docs/database/migrations.md)
- [Bộ hiện tại: 360 PDF, structured r2](docs/database/dataset_and_corpus.md)
- [Audit LLM dùng chung, client riêng từng module](docs/guides/llm_audit.md)
- [Khởi tạo dependencies](docs/guides/startup.md)
- [Ghép module](docs/modules/README.md)
- [Contracts nghiệp vụ](docs/contracts/data_contracts_v7_3_2.md), [schemas module](docs/contracts/module_contracts.schema.json)
- [Kiến trúc](docs/architecture/system_architecture.md), [trạng thái bước 5–7](docs/architecture/system_architecture.md#trạng-thái-triển-khai-bước-57)
- [Bàn giao nhóm C và cách nhóm D đọc đúng run](docs/group_c_handoff.md)

Ruleset `main`: PR bắt buộc, 0 approval, CI thành công và up-to-date, resolve discussions,
chỉ squash, chặn xóa/force push, không bypass.
