# Công cụ phát triển còn sử dụng

Folder này giữ công cụ tải dataset đã chốt, nạp workbook vào PostgreSQL và kiểm tra dữ liệu QA. Business modules không import `devtools`.

| File | Mục đích | Lệnh/nơi sử dụng |
|---|---|---|
| `dataset_download.py` | Tải/giải nén gói đúng phiên bản và checksum | `python -m scripts.dataset pull/check` |
| `database_schema.py` | Khai báo cột/kiểu/khóa của 50 bảng workbook | Reader, seed và tests |
| `database_seed.py` | Đọc/validate workbook và seed SQL theo transaction | `python -m scripts.local_db preview/seed/check` |
| `qa_schema.py` | Khai báo sáu bảng QA và tên sheet | Reader/seed |
| `qa_validation.py` | Kiểm tra manifest, split và multipart payload/checksum | Reader/seed và tests |
| `qa_runs.py` | Đổi ID cho input của run thử nghiệm mới | Tests persistence và chuẩn bị input cho run thử nghiệm |
| `upstream_fixtures.py` | Đọc C02/chunks/C03 và Context tham chiếu từ QA để dev bước 3–4 khi chưa có output bước 1–2 | Dev/eval nhóm B |

Đã bỏ các công cụ sinh PDF/synthetic scenarios, chia split và rebuild workbook/reference của release trước. Dataset, schema SQL và dữ liệu seed được giữ nguyên. Team tải gói DEV_VALIDATION bằng script dataset; không cần dựng lại dataset để bắt đầu dev.

Helpers dựng workbook/payload nhỏ cho tests nằm ở `backend/tests/seed_helpers.py`, không thuộc package cài đặt hoặc runtime.

Migration schema do Alembic trong `legal_checker/migrations/` quản lý. Runner và công cụ render SQL cũ đã xóa. Seed gọi Alembic upgrade trước, sau đó nhập rows trong transaction riêng.

Công cụ sinh đặc tả contracts/OpenAPI đã xóa. Bản JSON được giữ và cập nhật trực tiếp
trong `docs/`; tests chỉ đọc/kiểm tra chúng, không sinh lại file.
