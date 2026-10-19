# Các lệnh hỗ trợ phát triển

Chạy từ root repo, dùng Python trong `.venv` đã cài `backend[dev,dataset]`. Xem [tạo môi trường ảo](../docs/dev_setup.md) trước khi chạy lệnh.

| Script | Mục đích | Lệnh ví dụ | Hiện trạng |
|---|---|---|---|
| `dataset.py` | Tải/kiểm tra dataset DEV_VALIDATION theo manifest/hash | `python -m scripts.dataset pull` hoặc `check` | Đang dùng |
| `local_db.py` | Tạo DB, Alembic upgrade, preview/seed/check workbook | `python -m scripts.local_db init` / `preview` / `seed` / `check` | Đang dùng |
| `local_postgres.py` | Bật/tắt/kiểm tra PostgreSQL native trên Linux/macOS | `python -m scripts.local_postgres start` / `status` / `stop` | Tùy chọn cho người không dùng Docker; cần extra `[local-server]` |
| `ui_fixtures.py` | Xuất report C13 tham chiếu (QA EXPECTED, split DEV) làm mock cho frontend | `python -m scripts.ui_fixtures` hoặc `--case CA360_051` | Đang dùng; ghi vào `frontend/src/mocks/fixtures/` (Git bỏ qua) |

Ba script đầu phục vụ tải dataset, chạy PostgreSQL và setup/seed DB; `ui_fixtures` chỉ đọc DB để dựng giao diện. Mỗi module tự viết query/mapper
để dựng input từ DB theo [hướng dẫn JOIN sau seed](../docs/huong_dan_trien_khai_module_sau_seed.md).
Chưa có runner/evaluator CLI cho bước 5–7; người phụ trách viết chúng khi đã có implementation thật.

Các script rebuild workbook/PDF của release cũ (`optimize_workbook`, `synthetic_workbook`, `source_pdf_workbook`) đã xóa. Dataset hiện được tải từ release đã chốt; không cần dựng lại để bắt đầu làm module.

`dataset pull` tải files local, `local_db seed` ghi DB. Đọc/seed workbook và kiểm tra QA nằm trong `backend/src/devtools/`; business logic nằm trong `backend/src/legal_checker/modules/`.

`local_db init` dùng Alembic trong `legal_checker/migrations/`; runner SQL cũ đã xóa. `seed` cập nhật schema trước, sau đó nhập dữ liệu trong transaction riêng. Xem [tạo revision và tiếp nhận DB cũ](../docs/database_migrations.md).

Xem [hướng dẫn contracts máy đọc được](../docs/contracts/README.md) để cập nhật trực tiếp đặc tả JSON. Tests kiểm tra tính hợp lệ và đối chiếu với models hiện tại mà không ghi lại files.

`docs/openapi.design.json` là đặc tả API được commit cùng tài liệu. Backend không đọc
file này để chạy handlers. Công cụ sinh contracts/OpenAPI đã được xóa sau khi xuất đặc tả.
