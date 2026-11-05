# Cập nhật DB từ workbook đã được duyệt

Revision hiện tại: **user-reviewed-20261105**. Đây là bản metadata review mới của
dataset `v7.5.0-source-pdf360-r2-structured / supabase-public-v1`, không đổi schema
workbook hoặc bộ PDF nguồn.

| Thành phần | Giá trị |
|---|---|
| Workbook | `bang_du_lieu_runtime_v7_5_0_360_STRUCTURED_R2_SUPABASE_DEV_VALIDATION_USER_REVIEWED_20261105.xlsx` |
| Corpus | 240 DEV + 60 VALIDATION; thêm 32 QA regression |
| Legal knowledge version | `V750_LEGAL_KNOWLEDGE_USER_REVIEWED_20261105` |
| Knowledge SHA-256 | `df6ed7aa9f5100bfe68430b950d55542db752e7255c324e18be171ce0d0d3ade` |
| Workbook SHA-256 | `c77b43613918a95acb0845153218f52ec0edef855314397ccb670eaac0643f7f` |
| ZIP bytes | `143454238` |
| ZIP SHA-256 | `51fd0c109a1f77688af549cc08973ac7a1eb5ffea72a7c2505242340f1efd57d` |

## 1. Máy mới, DB chưa seed

Làm theo [cài môi trường](../guides/dev_setup.md), sao chép `.env.example` khi chưa
có `.env`, rồi chạy từ root repo:

```bash
python -m scripts.dataset pull
python -m scripts.dataset check
python -m scripts.local_db init
python -m scripts.local_db seed
python -m scripts.local_db check
```

Nếu maintainer chưa thay ZIP trên Drive, tải ZIP mới bằng trình duyệt và dùng:

```bash
python -m scripts.dataset pull --archive '/path/to/legal_compliance_v750_STRUCTURED_R2_SUPABASE_DEV_VALIDATION.zip'
```

ZIP cũ không còn khớp manifest và sẽ bị từ chối. Không sửa hash để bỏ qua lỗi.

`seed` kiểm tra checksum workbook theo manifest. Với đúng release reviewed,
snapshot mới được lưu với `review_status=HUMAN_VERIFIED`. Seeder không tự duyệt
workbook tự chỉnh sửa hoặc thay đổi snapshot lịch sử.

## 2. Máy đã seed bản cũ và cần giữ dữ liệu

Giữ workbook gốc đã seed. Bản cũ tiêu chuẩn có SHA-256
`e1f15b658d6ef511efa784eb09896adcda67befadbc51ae7411a90c1a4b29e61`.
Giữ `.env`, đặc biệt `DATABASE_URL` và cấu hình riêng của module.

Trước khi cập nhật, sao lưu DB bằng `pg_dump -Fc` hoặc công cụ backup PostgreSQL
đang dùng. Tạm dừng tạo assessment mới; đợi tất cả run `QUEUED`/`RUNNING` kết thúc.

Tải revision mới vào folder riêng để giữ nguyên bộ cũ:

```bash
python -m scripts.dataset pull \
  --destination data/private/v750_source_pdf360_r2_supabase_user_reviewed_20261105 \
  --archive '/path/to/legal_compliance_v750_STRUCTURED_R2_SUPABASE_DEV_VALIDATION.zip'
```

Đổi **chỉ `SEED_WORKBOOK_PATH`** trong `.env` thành:

```dotenv
SEED_WORKBOOK_PATH=data/private/v750_source_pdf360_r2_supabase_user_reviewed_20261105/bang_du_lieu_runtime_v7_5_0_360_STRUCTURED_R2_SUPABASE_DEV_VALIDATION_USER_REVIEWED_20261105.xlsx
```

Nâng schema, rồi chạy thử cập nhật trong transaction sẽ rollback:

```bash
python -m scripts.local_db init
python -m scripts.local_db update \
  --previous-workbook data/private/v750_source_pdf360_r2_supabase/bang_du_lieu_runtime_v7_5_0_360_STRUCTURED_R2_SUPABASE_DEV_VALIDATION.xlsx \
  --dry-run
```

Khi kết quả `dry_run` đúng, chạy lại để lưu:

```bash
python -m scripts.local_db update \
  --previous-workbook data/private/v750_source_pdf360_r2_supabase/bang_du_lieu_runtime_v7_5_0_360_STRUCTURED_R2_SUPABASE_DEV_VALIDATION.xlsx
python -m scripts.local_db check
```

Nếu workbook cũ ở nơi khác, thay đường dẫn `--previous-workbook`. CLI lấy version
và knowledge hash từ manifest khi tên workbook mới đúng release. `init` chỉ nâng
schema; `update` cập nhật dữ liệu. Không dùng `seed` để ghi đè release cũ.

## 3. Cơ chế giữ dữ liệu

- Đối chiếu checksum workbook cũ với receipt của DB, sau đó đối chiếu từng dòng cũ
  với DB. Dòng dev đã sửa và khác cả hai phiên bản làm toàn bộ update rollback.
- Chỉ cập nhật các PK thuộc workbook. Hợp đồng upload và dòng dev tự thêm được giữ.
- Giữ nguyên run, report versions, review, LLM audit, users và output có lineage.
  Case đã có run hoặc case pin giữ metadata phiên bản cũ để tái lập lịch sử.
- Giữ snapshot tri thức cũ bất biến, tạo snapshot reviewed mới với hash riêng.
- QA tham chiếu được thay bằng payload mới, kiểm tra multipart/checksum. Các trigger
  chống sửa QA chỉ tạm ngừng trên bảng liên quan trong transaction update đã khóa,
  rồi được bật lại trước commit; lỗi hoặc dry-run rollback cả dữ liệu lẫn trạng thái
  trigger. Bản QA cũ vẫn có trong workbook cũ và backup DB.
- Ghi receipt riêng tại `dev_meta.dataset_updates`; không sửa receipt seed gốc.
  Gọi lại cùng bản trả `already_applied`. Lịch sử update chống UPDATE/DELETE.

Không drop/truncate/reset DB và không gọi LLM trong quá trình update. Nếu có
xung đột, xem danh sách PK, giữ thay đổi dev và chọn DB mới hoặc giải quyết khác biệt
bằng review riêng; không sửa receipt để ép cập nhật.

## 4. Ứng dụng đang chạy và giới hạn của review metadata

API/worker giữ knowledge trong bộ nhớ từ lúc khởi tạo. Sau khi update DB, khởi động
lại API, worker và Beat để các lần chạy mới đọc snapshot mới. Nếu deployment cấu
hình `KNOWLEDGE_SNAPSHOT_SHA256`/`DEPLOYMENT_LEGAL_KNOWLEDGE_VERSION`, phải cập nhật
pin đúng revision mới trong cấu hình triển khai. Báo cáo cũ vẫn giữ version cũ.

Tri thức reviewed phản ánh việc chủ bộ dữ liệu xác nhận bộ tri thức. Flags runtime
trong workbook là review của **fixture synthetic**, không phải thao tác tự động
duyệt mọi PDF mới tải lên. Các giá trị thiếu, mâu thuẫn, scope/version chưa phân
giải, `UNKNOWN`/`INSUFFICIENT`, draft chờ review và negative QA fixtures được giữ.
Việc update không chạy lại inference, không biến báo cáo cũ thành kết quả mới và
không chứng minh toàn bộ pipeline đã đạt chất lượng phát hành.

## 5. Phát hành ZIP lên Drive

File ZIP và workbook nằm ngoài Git; chỉ commit manifest, tooling và hướng dẫn.
Trong Drive, dùng **Manage versions → Upload new version** trên ZIP cũ để giữ ID
`1hfaKo5uFtDFhDtvfPrTqTBbyDPNmdUDb`, giữ quyền Viewer public. Nếu upload thành file
mới, cập nhật `archive.url` trong manifest bằng link mới. Chỉ upload workbook riêng
sẽ không thay ZIP mà `scripts.dataset pull` tải.

Sau upload, chạy `scripts.dataset pull` với destination còn trống để kiểm tra
download thực tế. Chạy `--archive` chỉ xác minh bản local, chưa chứng minh Drive đã
phát hành đúng file.
