# PostgreSQL local và seed từ workbook

Mỗi dev có **một PostgreSQL riêng trên máy**, cùng cấu trúc bảng và cùng workbook seed.
Không cần Supabase để phát triển từng module.

```text
legal_checker_dev
├── knowledge    22 bảng: luật, requirements, criteria, rules, templates, quản trị knowledge
├── runtime      28 bảng: hợp đồng, chunks, evidence, case, kết quả, review, quyền
└── dev_meta      migration và lần seed; snapshots/run lineage nằm ở schema tương ứng
```

Workbook `bang_du_lieu_runtime_v7_4_9_RISK.xlsx` có 50 sheet dữ liệu và 5 sheet hướng dẫn.
Chỉ 50 sheet dữ liệu được tạo thành bảng SQL. File kiểm tra trên máy hiện tại có
**35.688 dòng**, gồm 90 hợp đồng, 7.820 chunks và 24 ca đánh giá.
Các bảng quản trị `phien_ban_trien_khai`, `duyet_tri_thuc`, `nhat_ky_ra_soat`,
`khoang_trong_tri_thuc` nằm trong `knowledge`; review và quyền theo case nằm trong `runtime`.

## 1. Cài dependencies và cấu hình

Từ thư mục gốc repo:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e './backend[dev]' -c constraints.txt
cp .env.example .env
mkdir -p data/private
```

Mỗi người nhận **cùng file Excel gốc** từ người quản lý dữ liệu, rồi đặt bản sao vào:

```text
data/private/bang_du_lieu_runtime_v7_4_9_RISK.xlsx
```

Hoặc sửa `SEED_WORKBOOK_PATH` trong `.env` thành đường dẫn workbook trên máy mình.
`.env`, workbook, dữ liệu DB và log trong `data/private/` được Git bỏ qua.
Repo chứa code tạo bảng và nhập dữ liệu; clone repo không tự tải workbook riêng của bạn.
CLI tự đọc `.env`; biến môi trường đã export được ưu tiên.

## 2. Bật PostgreSQL — chọn một cách

**Docker Compose:**

```bash
docker compose up -d --wait postgres
```

DB chỉ mở trên loopback `127.0.0.1`. Dữ liệu nằm trong volume `postgres_data`,
vẫn còn khi chạy `docker compose down`. Có thể đặt `POSTGRES_PASSWORD`/`POSTGRES_PORT`
trong `.env`; khi đổi phải cập nhật `DATABASE_URL` tương ứng.
Mật khẩu khởi tạo chỉ áp dụng lần đầu volume còn trống.

**Máy Linux/macOS không có Docker:**

```bash
pip install -e './backend[local-server]'
python -m scripts.local_postgres start
python -m scripts.local_postgres status
```

Gói optional cung cấp PostgreSQL 17.10 chạy bằng user hiện tại, không cần sudo.
Dữ liệu tại `data/private/postgres-local/cluster`, log tại
`data/private/postgres-local/server.log`. Cổng mặc định cũng là 5433.
Tắt bằng `python -m scripts.local_postgres stop`.
Nếu máy đã có PostgreSQL, dùng instance hiện có và sửa `DATABASE_URL`.

## 3. Tạo bảng, kiểm tra và seed

```bash
python -m scripts.local_db init
python -m scripts.local_db preview
python -m scripts.local_db seed
python -m scripts.local_db check
```

- `init`: tạo database nếu chưa có, áp dụng các migrations: 50 bảng workbook, 78 FK nền và các bảng snapshot/run lineage.
- `preview`: đọc workbook, kiểm tra tên sheet/cột, PK/FK, JSON, kiểu số/ngày và số dòng.
  Không ghi DB.
- `seed`: kiểm tra như preview, nhập cả workbook trong **một transaction**.
  Các bảng có vòng tham chiếu được xử lý bằng deferred foreign keys.
  Lỗi sẽ rollback dữ liệu được nhập trong lần seed đó.
- `check`: liệt kê số dòng từng bảng, danh sách `ca_id` và checksum workbook đã nhập.

Có thể chỉ rõ workbook từng lần:

```bash
python -m scripts.local_db seed --workbook '/path/to/bang_du_lieu_runtime_v7_4_9_RISK.xlsx'
```

Seed lại đúng file trả `already_seeded`, không thêm dòng trùng, không ghi đè dòng dev
đã sửa/thêm/xóa. Nếu một PK đã tồn tại trước lần seed đầu, seed cũng giữ dòng đó và
báo `skipped_existing`. Dùng DB mới khi muốn trở về toàn bộ baseline sạch.
Workbook khác checksum sẽ bị từ chối trên DB đã seed; hãy dùng DB riêng cho dataset mới.
CLI không tự drop/truncate bảng.

Ngày Excel dạng số được chuyển theo epoch của workbook; ngày nghiệp vụ dùng `DATE`,
thời gian audit dùng `TIMESTAMPTZ`. Timestamp không có timezone được quy ước UTC khi seed.
Các cờ `CO/KHONG/UNKNOWN` giữ dạng TEXT; cờ boolean 0/1 được chuyển thành BOOLEAN,
không đổi UNKNOWN thành false. Cột `_json` và criterion `dieu_kien` dùng JSONB;
`khuyen_nghi_danh_gia.dieu_kien_snapshot` là TEXT vì workbook có cả mô tả văn bản.
Formula hoặc ô Excel lỗi bị từ chối thay vì âm thầm nhập giá trị thiếu.

Checksum file seed được lưu riêng tại `dev_meta.seed_imports`.
Các checksum/snapshot phiên bản lịch sử trong dữ liệu được giữ nguyên.

## 4. Mở DB và xem bảng

Dùng DBeaver, pgAdmin hoặc công cụ PostgreSQL quen thuộc với cấu hình mặc định:

| Trường | Giá trị |
|---|---|
| Host | `127.0.0.1` |
| Port | `5433` |
| Database | `legal_checker_dev` |
| User | `legal_checker` |
| Password local | `legal_checker_local_only` |

```sql
SELECT tieu_chi_id, requirement_version_id, noi_dung, human_verified, trang_thai
FROM knowledge.tieu_chi_danh_gia ORDER BY tieu_chi_id;

SELECT ca_id, hop_dong_id, trang_thai, loai_du_lieu
FROM runtime.ca_danh_gia ORDER BY ca_id;
```

## 5. Từng người dùng dữ liệu gì?

| Phần phát triển | Input / bảng nên đọc | Output mẫu để đối chiếu |
|---|---|---|
| Document Intelligence | `runtime.hop_dong`, `tep_nguon` + PDF gốc riêng | Profile, chủ thể, chunks, viện dẫn, các bảng extraction/evidence |
| Scope + Temporal + Citation | Profile/chủ thể/mốc/viện dẫn; knowledge phạm vi, requirements, phiên bản và luật | `yeu_cau_ap_dung`, `phat_hien_vien_dan` |
| Retrieval | `yeu_cau_ap_dung`, chunks, knowledge criteria/versions | `ket_qua_truy_xuat` theo đúng `yeu_cau_ca_id` + `lan_chay_id` |
| Compliance + Risk + Recommendation | Applicable requirements, evidence, knowledge rules/templates; C09 riêng cho nhánh citation | `ket_qua_tieu_chi`, `ket_qua_tuan_thu`, `ket_qua_rui_ro`, `khuyen_nghi_danh_gia` |
| Integration + Review + Report | Case, deployment, các kết quả, quyền/review | `bao_cao_danh_gia`, `nhat_ky_review` |

Bộ runtime trong DB là **dữ liệu mẫu lấy từ workbook**, để module chưa hoàn thành vẫn có
input phát triển. Giữ nguyên `SYNTHETIC_DEMO`, `AI_DRAFT`, `human_verified`, review status
và nhãn nguồn. Không coi toàn bộ output mẫu là gold đã được người xác nhận.
URL/object_uri trong `tep_nguon` chỉ là thông tin nguồn; seed không tải PDF gốc.
Test parser/OCR vẫn cần PDF thật và kết quả mong đợi tương ứng.

SQL rows chưa tự trở thành contracts C01–C13: module cần map chúng sang DTO trong
`legal_checker.shared.contracts` rồi validate. Không join chỉ theo `requirement_id` khi
chạy nhiều case. Phải lọc `ca_id`, và với retrieval/C07/C09 phải chọn đúng `lan_chay_id`.

Ví dụ repository có sẵn cho người làm Retrieval:

```python
import os
from dotenv import load_dotenv
from legal_checker.modules.retrieval.repository import RetrievalDatasetRepository
from legal_checker.modules.legal_knowledge.postgres_repository import WorkbookKnowledgeRepository

load_dotenv()
url = os.environ["DATABASE_URL"]
retrieval = RetrievalDatasetRepository(url)
# Lấy ca_id thật từ lệnh local_db check.
rows = retrieval.load_input_rows(ca_id="CA_ID_TU_DB")
# rows: case + requirements (C05 source rows) + chunks + criteria của các phiên bản đó.
evidence = retrieval.load_seeded_evidence("CA_ID_TU_DB", "LAN_CHAY_ID_TU_DB")

knowledge = WorkbookKnowledgeRepository(url)
criteria = knowledge.criteria_for("REQUIREMENT_VERSION_ID_TU_DB")
rules = knowledge.decision_rules_for("TIEU_CHI_ID_TU_DB")
templates = knowledge.risk_templates_for("TIEU_CHI_ID_TU_DB")
```

Các method trả SQL rows giữ trạng thái xác minh; không tự kết luận áp dụng,
không gọi LLM và không duyệt knowledge. Module khác đặt query riêng trong
`modules/<module>/repository.py`; tạo connection dùng chung ở `core/postgres.py`.

## 6. Code nằm ở đâu?

| File | Mục đích |
|---|---|
| `compose.yaml` | DB Docker, lưu volume riêng |
| `scripts/local_postgres.py` | Server native khi không có Docker |
| `scripts/local_db.py` | CLI init/preview/seed/check |
| `backend/src/devtools/database_schema.py` | Danh sách 50 bảng, cột, kiểu và 78 FK cố định |
| `backend/src/devtools/database_migration.py` | Sinh SQL từ schema cố định |
| `backend/src/legal_checker/core/sql/001_workbook_v7_4_9.sql` | Migration 1, đóng gói cùng backend |
| `backend/src/devtools/database_seed.py` | Đọc Excel, validate, seed transaction và idempotency |
| `backend/src/legal_checker/core/postgres.py` | Connection dùng chung |
| `backend/src/legal_checker/core/migrations.py` | Áp dụng SQL migrations có checksum |
| `backend/src/legal_checker/core/sql/002_snapshots_and_runs.sql` | Snapshot knowledge, case/run pins và output lineage |
| `modules/legal_knowledge/postgres_repository.py` | Query criteria, rules, risk/templates |
| `modules/retrieval/repository.py` | Ghép input theo case và evidence theo case/run |

Migration đã áp dụng có checksum. Khi sửa schema, thêm migration kế tiếp, không sửa
migration 1 trên DB đã có dữ liệu. `backend/alembic/` vẫn là folder dự phòng;
CLI này dùng SQL migration trực tiếp, chưa cấu hình Alembic.

**API bước 5–7 đã dùng PostgreSQL.** `Knowledge` đầy đủ đọc 18 bảng nghiệp vụ,
lưu snapshot bất biến trong `knowledge.knowledge_snapshots`. `Store` ghi runtime normalized
và `assessment_runs`/`assessment_output_lineage` để tái hiện lịch sử.
Cấu hình `DATABASE_URL`; optional `KNOWLEDGE_SNAPSHOT_SHA256` để chọn snapshot cũ.
Hash snapshot là hash nội dung knowledge, độc lập với checksum file Excel.
Reader capture source tables khi khởi tạo; flags draft/unverified giữ nguyên.

Đọc input rows cho module qua CLI:

```bash
python -m scripts.db_module_input --case SEED_CA_001 --run SEED_RUN_SEED_CA_001
```

Đây là rows thật cần mapper/validation, không giả tạo criterion IDs/evidence đã được chọn.

## 7. Kiểm tra trên DB test riêng

```bash
TEST_DATABASE_URL='postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_test' \
  pytest -q -c backend/pyproject.toml
```

User DB test cần quyền CREATEDB. Tests tạo DB `legal_checker_test_<random>` riêng và xóa
sau khi chạy; không ghi `legal_checker_dev`. Tên DB trong biến test phải bắt đầu bằng
`legal_checker_test`. Không có biến này thì nhóm integration PostgreSQL được skip.
CI luôn bật PostgreSQL service và chạy nhóm test này bằng workbook nhỏ tổng hợp,
không phụ thuộc workbook riêng của bạn.
