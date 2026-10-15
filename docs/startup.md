# Khởi tạo backend từ PostgreSQL

Nếu chưa có môi trường Python của repo, làm theo [hướng dẫn tạo/kích hoạt `.venv`](dev_setup.md) trước.

Sau khi chạy `local_db init` và seed workbook, `create_app()` đọc cấu hình DB và
`build_services()` tạo Knowledge reader, assessment Store, audit sink và source storage dùng chung.

```python
from legal_checker.api.dependencies import build_services
from legal_checker.core.config import Settings
from legal_checker.main import create_app

settings = Settings.from_env()
services = build_services(settings)
api = create_app(settings=settings, services=services)
```

1. `Settings` đọc `.env`: DB URL, optional knowledge hash và cấu hình cache/timeout/giới hạn bytes nguồn.
2. `Knowledge(database_url, snapshot_sha256)` đọc SQL và tạo/lấy snapshot nội dung
   trong DB, tính hash rồi lập indices criteria/rules/versions. Không đọc file knowledge.
3. `Store(database_url)` cung cấp get/save PostgreSQL; mỗi thao tác mở transaction riêng.
4. `PostgresLlmAuditSink(database_url)` dùng bảng X02 có sẵn; constructor không gọi provider hoặc ghi log giả.
5. `CachedHttpSourceStorage` được tạo với cấu hình local; constructor không tải PDF hoặc tạo folder cache. Xem [cách dùng cho nhóm A](source_storage.md).
6. `Services` gom các dependencies, có `llm_audit` và `source_storage` để inject vào service của từng module. Các module không tự lấy environment/secret trong engine.
7. `create_app` gắn Services vào app và đăng ký routes. Đây chưa phải chạy HTTP server.

```bash
python -m scripts.local_db init
python -m scripts.local_db seed
uvicorn legal_checker.main:create_app --factory --host 127.0.0.1 --port 8000
```

Chạy `python -m scripts.local_db init` để Alembic cập nhật schema trước app; dùng `seed` để nạp workbook. API không tự chạy migration, nạp Excel hoặc duyệt knowledge. [Hướng dẫn Alembic](database_migrations.md).
Khi không chỉ định hash, reader capture source tables hiện tại vào snapshot dev bất biến.
Muốn replay snapshot cũ, export `KNOWLEDGE_SNAPSHOT_SHA256` bằng hash đã có trong DB.
Đổi source tables không thay nội dung reader đang dùng; khởi tạo reader mới để capture thay đổi.

Các POST chạy riêng bước 5–7 đã bỏ; API khởi chạy toàn bộ assessment vẫn cần triển khai.
GET run dùng Store; GET knowledge dùng Knowledge. Bước 5–7 cần triển khai trước khi nối luồng tính toán và lưu run.
Factory có thể nhận `Services(knowledge, memory_store)` trong unit tests để thay writer.

Các phần OCR/search/LLM/review/export/worker vẫn cần implementations riêng.
Xem [DB local](local_database.md) và [hướng dẫn nhóm](huong_dan_trien_khai_module_sau_seed.md).
