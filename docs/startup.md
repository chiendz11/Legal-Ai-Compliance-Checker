# Khởi tạo backend theo cấu trúc module

`legal_checker.main.create_app()` tạo FastAPI. `legal_checker.api.dependencies.build_services()` tạo hai đối tượng dùng chung: bộ đọc knowledge và nơi lưu assessment runs.

```python
from legal_checker.api.dependencies import build_services
from legal_checker.core.config import PROJECT_ROOT, Settings
from legal_checker.main import create_app

settings = Settings(
    knowledge_path=PROJECT_ROOT / "data/knowledge.json",
    database_path=PROJECT_ROOT / "data/private/runtime.sqlite3",
)
services = build_services(settings)
api = create_app(settings=settings, services=services)
```

1. `Settings(...)` chỉ ghi nhận đường dẫn, chưa mở file/DB.
2. `build_services(...)` gọi `Knowledge(...)` trong `modules/legal_knowledge/repository.py`: đọc JSON, tính SHA256 và lập bảng tra cứu criteria/rules/versions.
3. Hàm đó gọi `Store(...)` trong `modules/assessments/repository.py`: chuẩn bị SQLite và các bảng MVP còn thiếu, giữ kết quả đã có. Kết nối được mở/đóng cho mỗi thao tác qua `core/database.py`.
4. `Services(...)` gom hai đối tượng đã sẵn sàng; không tự chạy đánh giá.
5. `create_app(...)` gắn chúng vào `api.state.services` và đăng ký router. Vì đã truyền services nên không khởi tạo lại. Tạo app chưa tự bật HTTP server.

Khi không truyền services, `create_app()` đọc environment rồi gọi `build_services()` một lần cho mỗi app instance. Chạy từ root repo, sau khi cài `pip install -e './backend[dev]' -c constraints.txt`:

```bash
uvicorn legal_checker.main:create_app --factory --host 127.0.0.1 --port 8000
```

Với request pipeline, `api/dependencies.py:get_services` lấy các đối tượng đó; route gọi `modules/assessments/service.py:run_steps_5_7`. Service gọi workflow rồi lưu kết quả bằng repository.

```python
response = evaluate(request, knowledge)
saved = store.save(request, response)
```

Demo dùng SQLite tạm, chạy workflow và đọc lại kết quả:

```bash
python -m scripts.demo_startup
```

Code khởi tạo trước đây trong `bootstrap.py` đã chuyển vào `api/dependencies.py`. Tên `Services` vẫn là dataclass chứa dependency đã tạo, không phải một folder dịch vụ.

Khi integration test, truyền `Services(knowledge, memory_store)` qua `create_app(services=...)` để thay repository. Factory không tạo SQLite nếu services đã được cung cấp.

Các phần LLM, OCR, search, auth, report export và worker chưa được tự khởi tạo. [Backend README](../backend/README.md) ghi trạng thái từng folder.
