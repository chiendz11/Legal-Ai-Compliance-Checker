# Tải dataset cho mỗi thành viên

Nếu chưa có môi trường Python của repo, làm theo [hướng dẫn tạo/kích hoạt `.venv`](dev_setup.md) trước.

Repo giữ script và manifest chứa link/phiên bản/hash; dataset ở Drive và Supabase.
Mỗi thành viên tải về thư mục local được Git bỏ qua, rồi seed DB riêng như hiện tại.
Không cần API key Google Drive cho link ZIP public.

## Bắt đầu

Từ root repo, trong môi trường Python đã activate:

```bash
pip install -e './backend[dev,dataset]' -c constraints.txt
cp .env.example .env
python -m scripts.dataset pull
python -m scripts.dataset check
python -m scripts.local_db init
python -m scripts.local_db seed
```

Nếu đã có `.env`, giữ cấu hình của mình và đối chiếu SEED_WORKBOOK_PATH với manifest.
Lệnh tải chỉ chuẩn bị files; init/seed là các lệnh riêng, vẫn nhận workbook đầy đủ.
Không dùng các workbook chia nhỏ để seed.

## Lệnh tải làm gì?

1. Đọc `configs/dataset_dev_validation.json` và chọn folder từ SEED_WORKBOOK_PATH.
2. Nếu đủ 335 file và tất cả hash đúng: trả `already_present`, không tải lại.
3. Tải ZIP đúng link Drive vào thư mục tạm dưới `data/private/`.
4. Kiểm tra kích thước/SHA-256 ZIP, rồi kiểm tra các đường dẫn và file required.
5. Cài workbook, 300 text references, 32 controlled sources, README và CSV URL PDF.
6. Kiểm tra SHA-256 từng file và chuyển thư mục tạm thành folder dataset hoàn chỉnh.
7. Xóa ZIP/thư mục tạm; không ghi đè folder cũ hoặc thay đổi DB.

PDF không được giải nén bởi lệnh này. Nhóm A query `tep_nguon.object_uri` để tải PDF
public từ Supabase và kiểm tra `sha256`; bản PDF offline vẫn nằm trong ZIP trên Drive.
Text `dataset://` ánh xạ theo thư mục dataset local như hướng dẫn hiện tại.

## Drive private/quota hoặc dùng file đã tải

Link ZIP tự động cần cho phép "Anyone with the link → Viewer".
Downloader xử lý trang xác nhận của Drive, timeout và retry. Script không đọc cookie
đăng nhập trong trình duyệt. Với file chỉ chia sẻ theo email, hoặc Drive từ chối tải:

```bash
python -m scripts.dataset pull --archive /path/to/legal_compliance_v750_STRUCTURED_R2_SUPABASE_DEV_VALIDATION.zip
```

Nếu đổi nơi lưu ZIP mà bytes không đổi, override link bằng `--url` hoặc biến
DATASET_ARCHIVE_URL trong `.env`. Hash manifest vẫn được giữ để phát hiện sai gói:

```bash
python -m scripts.dataset pull --url 'https://drive.google.com/file/d/FILE_ID/view'
```

## Folder local khác bản

Script giữ nguyên files và báo lỗi nếu folder đã có file thiếu/khác hash. Chọn folder
riêng với `--destination`, rồi đặt SEED_WORKBOOK_PATH tương ứng nếu muốn dùng nó để seed.
Không tự thay workbook của DB đã seed hoặc thay pin/hash để bỏ qua kiểm tra.

## Khi phát hành dataset mới

Maintainer upload ZIP đã chốt, cập nhật URL, hash archive, hash file required, phiên bản
và destination trong manifest, rồi review/commit metadata. Link và hash đi cùng một bản.
Manifest DEV_VALIDATION không chứa MASTER/TEST labels hoặc dữ liệu hợp đồng, chỉ metadata.
Các regression tests của downloader dùng ZIP nhỏ tạo trong tests; CI không tải dataset
từ Drive hoặc cần quyền truy cập Drive của nhóm.
