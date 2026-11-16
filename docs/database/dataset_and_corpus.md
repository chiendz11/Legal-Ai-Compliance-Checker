# Tải dataset cho mỗi thành viên

Baseline hiện hành: [PDF360 v4 r2 — runtime và knowledge đã duyệt](../guides/dataset_pdf360_v4r2_runtime_20261110.md).
Gồm 240 DEV + 60 VALIDATION và 32 ca regression trong QA. Mỗi người dùng DB local
riêng; MASTER/TEST labels dành cho evaluator. Các biến thể cùng một họ PDF giữ
cùng split để tránh rò rỉ giữa DEV và TEST.

## Cài đặt

Chạy tại root repo, trong [môi trường Python đã activate](../guides/dev_setup.md):

```bash
pip install -e './backend[dev,dataset]' -c constraints.txt
python -m scripts.dataset pull --archive /path/to/legal_compliance_v750_PDF360_V4R2_20261110_DEV_VALIDATION.zip
python -m scripts.dataset check
python -m scripts.dataset cache-sources
python -m scripts.local_db init
python -m scripts.local_db seed
python -m scripts.local_db check
```

Trước khi init/seed, đặt `DATABASE_URL` sang DB mới và `SEED_WORKBOOK_PATH` sang
workbook trong release. Không chép đè `.env` đã có credentials. Xem đầy đủ giá
trị trong [hướng dẫn release](../guides/dataset_pdf360_v4r2_runtime_20261110.md#5-cài-vào-máy-thành-viên).

## Từng lệnh làm gì?

1. `pull` đọc manifest, kiểm ZIP/hash và từng file required. Dùng thư mục tạm rồi
   mới chuyển thành folder hoàn chỉnh; phát hiện file local khác hash sẽ giữ nguyên.
2. `check` kiểm hash file đã cài, không thay dữ liệu.
3. `cache-sources` đọc index đã pin, kiểm PDF/SHA-256 và tạo cache theo hash.
   Nhóm A lấy bytes qua shared storage. Không dùng URL Supabase cũ chứa PDF v2.
4. `init` chạy Alembic trên DB local riêng. `seed` nhập workbook đầy đủ và pin
   snapshot đã duyệt; gọi lại đúng workbook không ghi trùng.
5. `check` của local_db đọc tình trạng DB đã seed. Các lệnh tải/cache không tự sửa DB.

Gói hiện `LOCAL_ARCHIVE_READY`. Sau khi maintainer upload đúng ZIP, link public
có thể tải tự động bằng `python -m scripts.dataset pull`. Nếu Drive yêu cầu đăng
nhập hoặc hết quota, tải bằng trình duyệt rồi dùng `--archive`. Downloader không
đọc browser cookies. Dùng `--url` hoặc `DATASET_ARCHIVE_URL` chỉ thay nơi tải;
checksum vẫn phải khớp cùng gói.

## Giữ dữ liệu cũ và giới hạn đánh giá

Release đổi bytes PDF, chunks và output liên quan nên seed DB mới, không chạy
reviewed-flags update vào DB đang phát triển. Giữ folder/DB cũ và lịch sử. Không
sửa hash để vượt kiểm tra khi gói khác phiên bản.

Knowledge HUMAN_VERIFIED không tự xác minh output runtime. Literal source
reference hỗ trợ chấm 36 trường phụ lục; C02–C13 do engine sinh là reference
regression, chưa phải đáp án pháp lý độc lập cho toàn bộ 360 hợp đồng.
