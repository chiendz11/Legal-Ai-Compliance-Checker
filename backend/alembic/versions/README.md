# SQL migrations

Alembic chưa được cấu hình. Migrations ở `src/legal_checker/core/sql/` và được
`core/migrations.py` áp dụng theo version/checksum; không sửa migration đã áp dụng.

- 001: 50 bảng workbook.
- 002: knowledge snapshots và assessment pins/runs/output lineage.

Chạy `python -m scripts.local_db init` từ repo root.
