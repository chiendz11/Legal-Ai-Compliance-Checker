# Khởi tạo backend từ PostgreSQL

Sau khi chạy `local_db init` và seed workbook, `create_app()` đọc cấu hình DB và
`build_services()` tạo hai dependencies dùng chung.

```python
from legal_checker.api.dependencies import build_services
from legal_checker.core.config import Settings
from legal_checker.main import create_app

settings = Settings.from_env()
services = build_services(settings)
api = create_app(settings=settings, services=services)
```

1. `Settings` giữ `database_url` và optional `knowledge_snapshot_sha256`, đọc `.env`.
2. `Knowledge(database_url, snapshot_sha256)` đọc SQL và tạo/lấy snapshot nội dung
   trong DB, tính hash rồi lập indices criteria/rules/versions. Không đọc file knowledge.
3. `Store(database_url)` cung cấp get/save PostgreSQL; mỗi thao tác mở transaction riêng.
4. `Services` gom hai dependency. Các module không tự lấy environment/secret trong engine.
5. `create_app` gắn Services vào app và đăng ký routes. Đây chưa phải chạy HTTP server.

```bash
python -m scripts.local_db init
python -m scripts.local_db seed
uvicorn legal_checker.main:create_app --factory --host 127.0.0.1 --port 8000
```

Migration cần chạy trước app. API không tự nạp Excel và không tự duyệt knowledge.
Khi không chỉ định hash, reader capture source tables hiện tại vào snapshot dev bất biến.
Muốn replay snapshot cũ, export `KNOWLEDGE_SNAPSHOT_SHA256` bằng hash đã có trong DB.
Đổi source tables không thay nội dung reader đang dùng; khởi tạo reader mới để capture thay đổi.

Pipeline HTTP → assessments service → workflow → engines → PostgreSQL Store.
Factory có thể nhận `Services(knowledge, memory_store)` trong unit tests để thay writer.
Export schemas dùng dependencies rỗng và không chạy handlers; không dùng app export để phục vụ HTTP.

Các phần OCR/search/LLM/review/export/worker vẫn cần implementations riêng.
Xem [DB local](local_database.md) và [hướng dẫn nhóm](huong_dan_trien_khai_module_sau_seed.md).
