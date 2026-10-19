# Alembic: quản lý cấu trúc PostgreSQL

Alembic quản lý **bảng, cột, khóa, index, trigger và thay đổi cấu trúc**. Script seed quản lý **dữ liệu lấy từ workbook**. Khi thêm cột cho module, viết migration; khi nạp dataset vào DB local mới, chạy seed.

Repositories tiếp tục dùng psycopg và SQL như hiện tại. SQLAlchemy được dùng cho kết nối của Alembic; không yêu cầu chuyển modules sang ORM.

## 1. Cài đặt và chạy trên DB local

Từ root repo, sau khi kích hoạt `.venv` và bật PostgreSQL:

```bash
python -m pip install -e './backend[dev,dataset]' -c constraints.txt
python -m scripts.local_db init
python -m alembic -c backend/alembic.ini current
python -m alembic -c backend/alembic.ini heads
```

`init` tạo database nếu chưa tồn tại, rồi chạy Alembic tới `head`. CLI Alembic trực tiếp cần database đã tồn tại. URL lấy từ `DATABASE_URL` trong môi trường hoặc `.env`; biến đã export được ưu tiên. Không ghi credentials vào `alembic.ini`.

Ba revision nền hiện tại:

| Revision | Nội dung |
|---|---|
| `0001_workbook` | 50 bảng workbook, các FK nền và `dev_meta.seed_imports` |
| `0002_snapshots` | Knowledge snapshots, case/run pins và output lineage |
| `0003_qa` | Sáu bảng QA, indexes và bảo vệ dữ liệu QA bất biến |

Revision tiếp theo:

| Revision | Nội dung |
|---|---|
| `0004_workflow_runs` | `runtime.workflow_runs` (trạng thái run, tiến độ stage, draft) và `runtime.report_versions` (C13 bất biến, file export) của nhóm D |

Xem lịch sử bằng:

```bash
python -m alembic -c backend/alembic.ini history --verbose
```

Alembic lưu revision hiện tại trong `dev_meta.alembic_version`. Chạy `init` hoặc `upgrade head` nhiều lần không chạy lại revision đã áp dụng.

## 2. Nếu đã seed DB bằng runner cũ

Giữ nguyên `DATABASE_URL` trỏ tới DB local của mình và chạy:

```bash
python -m scripts.local_db init
python -m alembic -c backend/alembic.ini current
```

Trước khi tiếp nhận, hệ thống đối chiếu:

1. Lịch sử `dev_meta.schema_migrations` có liên tục từ migration 1 không.
2. Checksum trong lịch sử và ba SQL baseline có khớp bản đã chốt không.
3. Cấu trúc thực tế có khớp baseline tương ứng không: bảng/cột, kiểu dữ liệu, default, constraints, indexes, triggers và functions thuộc schema quản lý.

Nếu khớp, hệ thống ghi revision Alembic tương ứng rồi áp dụng các revision còn thiếu. DB cũ đang ở migration 3 được tiếp nhận tại `0003_qa`; không chạy lại SQL nền, không seed lại và không xóa dữ liệu. Bảng `schema_migrations` cũ được giữ làm lịch sử, không còn được cập nhật.

Nếu schema/checksum lệch hoặc có bảng nghiệp vụ nhưng không có lịch sử, lệnh dừng và transaction migration rollback. Người đã tự sửa cấu trúc DB cần đối chiếu thay đổi trước; không dùng `alembic stamp head` để bỏ qua kiểm tra. Có thể dùng DB local mới rồi seed lại khi muốn baseline sạch; giữ DB cũ để bảo toàn phần đang làm.

Việc đối chiếu này dành cho lần chuyển từ runner cũ. Sau khi chuyển, Alembic dựa vào revision history; nó không tự kiểm tra mọi thay đổi DDL thủ công hay cung cấp checksum cho mọi revision mới.

## 3. Seed dữ liệu vẫn dùng lệnh hiện tại

Trên DB mới, sau khi [tải dataset](dataset_download.md):

```bash
python -m scripts.local_db preview
python -m scripts.local_db seed
python -m scripts.local_db check
```

`seed` validate workbook, đảm bảo schema tới Alembic head, rồi nhập dữ liệu trong transaction riêng. Nếu nhập lỗi, rows và marker của lần seed đó rollback; schema đã nâng cấp vẫn giữ. Seed lại cùng checksum trả `already_seeded`, giữ các thay đổi dữ liệu dev. Workbook khác checksum cần DB riêng như trước.

Alembic không tự tải PDF hoặc workbook và không thay thế seed. Pull code có migration mới chỉ cần chạy `init`, không cần nhập lại toàn bộ dataset.

## 4. Người phát triển module thêm migration như thế nào?

Ví dụ nhóm A cần cột `parser_version` trong `runtime.hop_dong`. Đây chỉ là ví dụ, chưa có cột/revision này trong repo.

Trước hết đồng bộ nhánh và xem head hiện tại, rồi tạo revision:

```bash
python -m alembic -c backend/alembic.ini heads
python -m alembic -c backend/alembic.ini revision -m "add parser version to contracts"
```

Alembic sinh file trong `backend/src/legal_checker/migrations/versions/`. Giữ các biến `revision`, `down_revision`, `branch_labels`, `depends_on` được sinh ra; sửa phần imports và hai hàm:

```python
from alembic import op
import sqlalchemy as sa

# Giữ nguyên metadata revision/down_revision của file được Alembic tạo.


def upgrade() -> None:
    op.add_column(
        "hop_dong",
        sa.Column("parser_version", sa.Text(), nullable=True),
        schema="runtime",
    )


def downgrade() -> None:
    op.drop_column("hop_dong", "parser_version", schema="runtime")
```

Cột nullable giúp dữ liệu seed hiện có tiếp tục hợp lệ. Khi cần NOT NULL, thiết kế cách backfill dữ liệu trước khi bật constraint. Bản template mới cố ý phát sinh `NotImplementedError` cho tới khi người viết điền migration; không được để revision rỗng rồi coi như đã đổi schema.

Chạy và kiểm tra:

```bash
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini current
```

Thêm integration test trên DB test riêng để xác nhận thay đổi và dữ liệu hiện có. Nếu thay đổi contract/schema workbook, cập nhật cả DTO, DB catalog, mapper/seed tương ứng; thêm migration không tự cập nhật những phần đó. Commit revision cùng code sử dụng nó và tài liệu thay đổi schema. Sau khi merge, các thành viên khác chạy `python -m scripts.local_db init` trên DB của mình.

Không sửa revision đã chia sẻ hoặc ba SQL baseline; thêm revision tiếp theo. Repo hiện dùng revisions viết tay, chưa cấu hình SQLAlchemy model metadata cho `--autogenerate`, và chưa hỗ trợ `upgrade --sql` offline.

## 5. Khi hai người cùng thêm revision

Chạy `heads` sau khi ghép nhánh. Nếu có hai head do hai migration độc lập cùng phát triển từ một revision:

```bash
python -m alembic -c backend/alembic.ini heads
python -m alembic -c backend/alembic.ini merge heads -m "merge module schema revisions"
```

Kiểm tra các thay đổi có xung đột bảng/cột hoặc phụ thuộc nhau không trước khi tạo merge revision. Merge revision không tự giải quyết xung đột SQL. Khi chỉ cần nối hai nhánh độc lập, thân `upgrade`/`downgrade` của merge revision có thể là `pass`; template hiện yêu cầu điền rõ. Chạy lại trên DB mới và DB đã nâng cấp để xác nhận đường nâng cấp.

PostgreSQL advisory lock tuần tự hóa các lệnh upgrade trên cùng DB; helper Python có thêm lock để bảo vệ context Alembic khi bị gọi từ nhiều threads trong cùng process.

## 6. Rollback và vị trí code

Ba revision baseline là **forward-only**: không hỗ trợ downgrade xóa cả bộ bảng và dữ liệu. Khi cần hủy baseline, khôi phục backup hoặc tạo DB local mới. Migration mới có thể viết `downgrade` nếu thao tác đảo ngược phù hợp; việc xóa cột sẽ mất dữ liệu cột đó. Chỉ thử rollback trên DB test hoặc DB có backup phù hợp.

| Vị trí | Trách nhiệm |
|---|---|
| `backend/alembic.ini` | Điểm vào CLI; trỏ tới migration package |
| `backend/src/legal_checker/migrations/env.py` | Cấu hình PostgreSQL, transaction, lock và tiếp nhận lịch sử cũ |
| `backend/src/legal_checker/migrations/versions/` | Các revision Alembic chạy theo quan hệ `down_revision` |
| `backend/src/legal_checker/migrations/sql/` | Ba SQL baseline cũ, giữ nguyên bytes/checksums |
| `backend/src/legal_checker/migrations/manager.py` | Helper upgrade cho CLI seed/tests và kiểm tra lịch sử cũ |
| `backend/src/legal_checker/migrations/schema_state.py` | Đọc fingerprints cấu trúc cho lần tiếp nhận DB cũ |
| `backend/src/legal_checker/migrations/legacy_baselines.json` | Fingerprints/checksums tham chiếu cố định; không phải knowledge/runtime dataset |
| `backend/src/devtools/database_seed.py` | Đọc workbook, validate và nhập dữ liệu |

Các file runner `core/migrations.py` và renderer `devtools/database_migration.py` đã xóa. SQL nền đã chuyển từ `core/sql/` sang migration package; không tồn tại hai cơ chế migrate song song. Migration resources được đóng gói cùng backend để CLI vẫn hoạt động khi cài package.
