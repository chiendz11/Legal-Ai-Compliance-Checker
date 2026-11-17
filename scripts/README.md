# Các lệnh hỗ trợ phát triển

Chạy từ root repo, dùng Python trong `.venv` đã cài `backend[dev,dataset]`. Xem [tạo môi trường ảo](../docs/guides/dev_setup.md) trước khi chạy lệnh.

| Script | Mục đích | Lệnh ví dụ | Hiện trạng |
|---|---|---|---|
| `dataset.py` | Tải/kiểm tra dataset DEV_VALIDATION theo manifest/hash | `python -m scripts.dataset pull` hoặc `check` | Đang dùng |
| `local_db.py` | Tạo DB, Alembic upgrade, preview/seed/update/check workbook | `python -m scripts.local_db init` / `preview` / `seed` / `update` / `check` | Đang dùng |
| `local_postgres.py` | Bật/tắt/kiểm tra PostgreSQL native trên Linux/macOS | `python -m scripts.local_postgres start` / `status` / `stop` | Tùy chọn cho người không dùng Docker; cần extra `[local-server]` |
| `eval_assessment.py` | Chạy đủ bước 1–7 trên một split (mặc định VALIDATION) và so với tham chiếu bạc: phạm vi, áp dụng, kết luận quy định, kết luận điểm kiểm tra | `python -m scripts.eval_assessment` hoặc `--limit 3 --llm` (tốn phí AI) | Đang dùng; ghi JSON/CSV vào `data/private/eval/` |
| `ui_fixtures.py` | Xuất report C13 tham chiếu (QA EXPECTED, split DEV) làm mock cho frontend | `python -m scripts.ui_fixtures` hoặc `--case CA360_051` | Đang dùng; ghi vào `frontend/src/mocks/fixtures/` (Git bỏ qua) |

Ba script đầu phục vụ tải dataset, chạy PostgreSQL và setup/seed DB; `ui_fixtures` chỉ đọc DB để dựng giao diện. Mỗi module tự viết query/mapper
để dựng input từ DB theo [hướng dẫn JOIN sau seed](../docs/modules/README.md).
`eval_assessment` là evaluator đầu-cuối cho bước 1–7; tham chiếu QA là bạc (`legal_gold=false`) nên độ khớp không phải độ chính xác pháp lý.

Các script rebuild workbook/PDF của release cũ (`optimize_workbook`, `synthetic_workbook`, `source_pdf_workbook`) đã xóa. Dataset hiện được tải từ release đã chốt; không cần dựng lại để bắt đầu làm module.

`dataset pull` tải files local, `local_db seed` ghi DB. Đọc/seed workbook và kiểm tra QA nằm trong `backend/src/devtools/`; business logic nằm trong `backend/src/legal_checker/modules/`.

`local_db init` dùng Alembic trong `legal_checker/migrations/`; runner SQL cũ đã xóa. `seed` cập nhật schema trước, sau đó nhập dữ liệu trong transaction riêng. Xem [tạo revision và tiếp nhận DB cũ](../docs/database/migrations.md).

Xem [hướng dẫn contracts máy đọc được](../docs/contracts/README.md) để cập nhật trực tiếp đặc tả JSON. Tests kiểm tra tính hợp lệ và đối chiếu với models hiện tại mà không ghi lại files.

`docs/architecture/openapi.design.json` là đặc tả API được commit cùng tài liệu. Backend không đọc
file này để chạy handlers. Công cụ sinh contracts/OpenAPI đã được xóa sau khi xuất đặc tả.

`local_db update` dành cho các revision tương thích như reviewed-flags, áp dụng trên
baseline đúng checksum trong một transaction. TEAM_BASELINE_20261107 thay identities
và runtime nên CLI yêu cầu DB mới, giữ DB/lịch sử cũ. Xem
[hướng dẫn baseline](../docs/guides/dataset_team_baseline_20261107.md).

`python -m scripts.local_db align-runtime` tạo snapshot catalog bổ sung bất biến
từ đúng TEAM 20261107 đã seed; lệnh in SHA mới để cấu hình API/worker. Không ghi
đè workbook, snapshot hoặc reports cũ. [Chi tiết](../docs/guides/complete_runtime_alignment_20261108.md).

`python -m scripts.local_db align-content-defaults --parent-sha256 <SHA>` tạo
revision source-checked cho rule phương thức bàn giao/bảo lưu sở hữu. Parent hash
và source binding được kiểm tra; không đổi pin lịch sử. Xem [hướng dẫn v4](../docs/guides/baseline_v4_civil_defaults_20261109.md).
