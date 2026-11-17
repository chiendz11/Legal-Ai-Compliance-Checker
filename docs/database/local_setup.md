# PostgreSQL local và seed từ workbook

Baseline hiện hành: [PDF360 v4 r2 — runtime và knowledge đã duyệt](../guides/dataset_pdf360_v4r2_runtime_20261110.md). Manifest đã `PUBLISHED` lên Google Drive; chạy `python -m scripts.dataset pull` (hoặc `--archive` nếu đã tải sẵn ZIP).

Nếu chưa có môi trường Python của repo, làm theo [hướng dẫn tạo/kích hoạt `.venv`](../guides/dev_setup.md) trước.

Mỗi dev có **một PostgreSQL riêng trên máy**, cùng cấu trúc bảng và cùng workbook seed.
Không cần Supabase để phát triển từng module.

```text
legal_checker_dev_pdfv4r2_20261110
├── knowledge    22 bảng workbook: luật, criteria, rules, templates và quản trị
├── runtime      28 bảng workbook: hợp đồng, chunks, evidence và kết quả
├── qa           6 bảng: split, payload/assertions tham chiếu và kiểm tra nguồn
└── dev_meta     alembic_version và checksum lần seed
```

Các migrations bổ sung immutable knowledge snapshots, run snapshots và DTO lineage ngoài 50 bảng workbook. Bộ hiện tại là **v7.5.0-pdf360-v4r2-runtime-20261110**, storage revision **bundled-pdf-v4r2**. Gói DEV_VALIDATION có **240 DEV + 60 VALIDATION**, **32 ca regression riêng trong QA**, các dòng nghiệp vụ/QA theo manifest PDF360_V4R2_20261110.

Mỗi thành viên tải cùng gói DEV_VALIDATION rồi seed vào DB local riêng. MASTER chứa đáp án TEST dành cho evaluator; TEST_INPUTS có 60 ca chỉ PDF/intake. Xem [dataset hiện tại](dataset_and_corpus.md).

## 1. Cài dependencies và cấu hình

Từ thư mục gốc repo:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e './backend[dev,dataset]' -c constraints.txt
cp .env.example .env
python -m scripts.dataset pull --archive /path/to/legal_compliance_v750_PDF360_V4R2_20261110_DEV_VALIDATION.zip
python -m scripts.dataset check
python -m scripts.dataset cache-sources
```

Script tải tự tạo `data/private/v750_pdf360_v4r2_runtime_20261110/`. Workbook dùng để seed là:

```text
data/private/v750_pdf360_v4r2_runtime_20261110/bang_du_lieu_v7_5_0_PDF360_V4R2_20261110_DEV_VALIDATION.xlsx
```

`.env.example` đã đặt `SEED_WORKBOOK_PATH` và `DATABASE_URL` cho bộ này. Nếu `.env` đã tồn tại, cập nhật hai biến tương ứng thay vì ghi đè cấu hình riêng. CLI đọc `.env`; biến môi trường đã export được ưu tiên.

Repo giữ code và manifest, không giữ dataset. `.env`, workbook, dữ liệu DB và log trong `data/private/` được Git bỏ qua. ZIP mới được bàn giao local; link Drive chỉ dùng sau khi xuất bản đúng bytes. Gói có 300 PDF v4 r2; `runtime.tep_nguon.object_uri` là dataset URI, chạy `cache-sources` để đọc qua cache đã kiểm hash. [Cách tải và xử lý Drive/quota](dataset_and_corpus.md).

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

- `init`: tạo database nếu chưa có, chạy Alembic tới head: 50 bảng workbook, 78 FK nền và các bảng snapshot/run lineage/QA. DB cũ được kiểm tra trước khi tiếp nhận lịch sử.
- `preview`: đọc schema, kiểu dữ liệu và số dòng. Workbook nhỏ được kiểm PK/FK/QA đầy đủ trong bộ đọc; workbook lớn dùng streaming, còn FK và QA multipart được kiểm khi seed trong cùng transaction. Receipt VALIDATION của release bổ sung kiểm tra spans/hash/split.
  Không ghi DB.
- `seed`: kiểm tra như preview, chạy Alembic tới head trước, rồi nhập cả 50 bảng nghiệp vụ và 6 bảng QA trong **một transaction dữ liệu riêng**.
  Các bảng có vòng tham chiếu được xử lý bằng deferred foreign keys.
  Lỗi sẽ rollback dữ liệu được nhập trong lần seed đó; schema Alembic đã cập nhật vẫn được giữ.
- `check`: liệt kê số dòng từng bảng, danh sách `ca_id` và checksum workbook đã nhập.

Có thể chỉ rõ workbook từng lần:

```bash
python -m scripts.local_db seed --workbook '/path/to/bang_du_lieu_v7_5_0_PDF360_V4R2_20261110_DEV_VALIDATION.xlsx'
```

Seed lại đúng file trả `already_seeded`, không thêm dòng trùng, không ghi đè dòng dev
đã sửa/thêm/xóa. Nếu một PK đã tồn tại trước lần seed đầu, seed cũng giữ dòng đó và
báo `skipped_existing`. Dùng DB mới khi muốn trở về toàn bộ baseline sạch.
Workbook khác checksum bị từ chối bởi seed. PDF360_V4R2_20261110 dựng lại identities/output nên seed DB mới; luồng [reviewed update](reviewed_dataset_update.md) chỉ dành revision tương thích, không áp dụng cho release này.
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
| Database | `legal_checker_dev_pdfv4r2_20261110` |
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
| Document Intelligence | `runtime.hop_dong`, `tep_nguon` + bytes PDF từ public URL | Profile, chủ thể, chunks, viện dẫn, các bảng extraction/evidence |
| Scope + Temporal + Citation | Profile/chủ thể/mốc/viện dẫn; knowledge phạm vi, requirements, phiên bản và luật | `yeu_cau_ap_dung`, `phat_hien_vien_dan` |
| Retrieval | `yeu_cau_ap_dung`, chunks, knowledge criteria/versions | `ket_qua_truy_xuat` theo đúng `yeu_cau_ca_id` + `lan_chay_id` |
| Compliance + Risk + Recommendation | Applicable requirements, evidence, knowledge rules/templates; C09 riêng cho nhánh citation | `ket_qua_tieu_chi`, `ket_qua_tuan_thu`, `ket_qua_rui_ro`, `khuyen_nghi_danh_gia` |
| Integration + Review + Report | Case, deployment, các kết quả, quyền/review | `bao_cao_danh_gia`, `nhat_ky_review` |

Bộ runtime trong DB là **dữ liệu mẫu lấy từ workbook**, để module chưa hoàn thành vẫn có
input phát triển. Giữ nguyên nhãn nguồn synthetic/reference, `human_verified`, review status
và các flags uncertainty. Không coi toàn bộ output mẫu là gold đã được người xác nhận.
Public URL trong `tep_nguon.object_uri` là nguồn để nhóm A tải PDF; seed không tự tải PDF.
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
| `scripts/local_db.py` | CLI init/preview/seed/update/check |
| `scripts/dataset.py` | Tải/kiểm tra gói DEV_VALIDATION theo manifest |
| `backend/src/devtools/qa_schema.py`, `qa_validation.py` | Khai báo QA sheets và kiểm tra split/payload/hash khi seed |
| `backend/src/devtools/database_schema.py` | Danh sách 50 bảng, cột, kiểu và 78 FK cố định |
| `backend/alembic.ini` | Cấu hình CLI Alembic; URL lấy từ `.env`/`DATABASE_URL` |
| `backend/src/legal_checker/migrations/versions/` | Lịch sử Alembic revisions; thêm revision mới tại đây |
| `backend/src/legal_checker/migrations/sql/001_workbook_v7_4_9.sql` | SQL baseline 50 bảng, giữ nguyên nội dung để nhận diện DB cũ |
| `backend/src/devtools/database_seed.py` | Đọc Excel, validate, seed transaction và idempotency |
| `backend/src/legal_checker/core/postgres.py` | Connection dùng chung |
| `backend/src/legal_checker/migrations/manager.py`, `env.py` | Chạy Alembic và kiểm tra DB cũ trước khi tiếp nhận |
| `backend/src/legal_checker/migrations/sql/002_snapshots_and_runs.sql` | Snapshot knowledge, case/run pins và output lineage |
| `backend/src/legal_checker/migrations/sql/003_evaluation_workbook.sql` | Các bảng QA của workbook đánh giá |
| `backend/src/legal_checker/migrations/legacy_baselines.json` | Fingerprints/checksums cố định để đối chiếu schema runner cũ; không phải dataset |
| `modules/legal_knowledge/postgres_repository.py` | Query criteria, rules, risk/templates |
| `modules/retrieval/repository.py` | Ghép input theo case và evidence theo case/run |

Alembic lưu revision hiện tại trong `dev_meta.alembic_version`. Khi sửa schema, thêm revision
trong `backend/src/legal_checker/migrations/versions/`; không sửa ba SQL baseline hoặc revision đã chia sẻ.
`python -m scripts.local_db init` gọi Alembic upgrade head. DB cũ giữ `schema_migrations` làm lịch sử;
runner mới không ghi thêm vào bảng đó. Xem [lệnh tạo revision, xử lý DB cũ và rollback](migrations.md).

**Không có POST chạy riêng bước 5–7; GET run/knowledge vẫn dùng PostgreSQL.** `Knowledge` đầy đủ đọc 18 bảng nghiệp vụ,
lưu snapshot bất biến trong `knowledge.knowledge_snapshots`. `Store` ghi runtime normalized
và `assessment_runs`/`assessment_output_lineage` để tái hiện lịch sử.
Cấu hình `DATABASE_URL`; optional `KNOWLEDGE_SNAPSHOT_SHA256` để chọn snapshot cũ.
Hash snapshot là hash nội dung knowledge, độc lập với checksum file Excel.
Reader capture source tables khi khởi tạo; không tự duyệt các flags. Với gói reviewed đúng manifest, seeder đăng ký snapshot `HUMAN_VERIFIED` đã được người dùng phê duyệt.

Mỗi module tự đọc input qua repository và mapper của mình. Các query chọn đúng case/run,
JOIN bảng và chuyển rows thành DTO nằm trong [hướng dẫn sau seed](../huong_dan_trien_khai_module_sau_seed.md).

## 7. Kiểm tra trên DB test riêng

```bash
TEST_DATABASE_URL='postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_test' \
  pytest -q -c backend/pyproject.toml
```

User DB test cần quyền CREATEDB. Tests tạo DB `legal_checker_test_<random>` riêng và xóa
sau khi chạy; không ghi DB dev hiện tại. Tên DB trong biến test phải bắt đầu bằng
`legal_checker_test`. Không có biến này thì nhóm integration PostgreSQL được skip.
CI luôn bật PostgreSQL service và chạy nhóm test này bằng workbook nhỏ tổng hợp,
không phụ thuộc workbook riêng của bạn.

## 8. Revision tri thức hiện hành

Bản hiện hành là `v7.5.0-pdf360-v4r2-runtime-20261110`, có 240 DEV + 60 VALIDATION và 32 ca regression. Tri thức mang nhãn `V750_KNOWLEDGE_OWNER_APPROVED_20261110`; SHA nội dung là `4ab2d7ea296ea908e25c09fcb6d5f073f1ebe1917678b36390f803b1c725804a`.

`seed` nhận diện workbook đúng manifest và pin snapshot `HUMAN_VERIFIED`: chủ dự án đã chấp nhận 479 criteria, 1.916 decision rules và 9 ngoại lệ. Dữ kiện extraction và kết quả AI có review riêng. Runtime/QA dựng lại theo cùng PDF v4 r2 và snapshot; reference engine vẫn là SILVER. Xem [baseline guide](../guides/dataset_pdf360_v4r2_runtime_20261110.md).

DB đã seed bản cũ được giữ nguyên. Với PDF360_V4R2_20261110, tạo DB mới theo guide hiện hành; không seed đè hoặc chạy reviewed update lên DB cũ.
