# Khởi tạo ứng dụng và tên folder

`bootstrap.py` tạo các đối tượng kỹ thuật mà API và workflows cần dùng. Hiện có hai đối tượng: bộ đọc knowledge JSON và nơi lưu kết quả đánh giá SQLite.

## Khởi tạo từng bước

Chạy đoạn sau từ thư mục repo, trong môi trường đã cài dependencies:

```python
from app.bootstrap import build_services
from app.main import create_app
from app.shared.config import PROJECT_ROOT, Settings

# Chỉ khai báo hai đường dẫn; chưa đọc JSON hoặc mở SQLite.
settings = Settings(
    knowledge_path=PROJECT_ROOT / "data/knowledge.json",
    database_path=PROJECT_ROOT / "data/private/runtime.sqlite3",
)

# Đọc JSON, tính checksum, lập indexes; tạo SQLite và các bảng còn thiếu.
services = build_services(settings)

# Truyền hai đối tượng đã khởi tạo vào FastAPI để các routes dùng chung.
api = create_app(settings=settings, services=services)

print(len(services.knowledge.criteria))  # 356 với snapshot hiện tại
print(services.assessments.get("CASE_DEMO", "RUN_DEMO"))  # None nếu chưa lưu
```

`Settings` chứa cấu hình, `services` chứa đối tượng đã sẵn sàng thực hiện công việc. `Services` là dataclass gom hai đối tượng; tên này không chỉ tới một folder services hoặc tự tạo module nghiệp vụ.

Code tương ứng bên trong `bootstrap.py`:

```python
def build_services(settings: Settings) -> Services:
    knowledge = Knowledge(settings.knowledge_path)
    assessment_store = Store(settings.database_path)
    return Services(knowledge=knowledge, assessments=assessment_store)
```

- `Knowledge(...)` đọc bytes JSON, tính SHA256, kiểm tra schema và lập các dictionary tra cứu criterion/rule/requirement. Nguồn knowledge hiện tại vẫn là JSON.
- `Store(...)` tạo folder/file SQLite khi chưa có và tạo các bảng runtime còn thiếu. Nó giữ đường dẫn DB; mỗi lần `get`/`save` mới mở connection và đóng sau thao tác. Khởi tạo không xóa kết quả đã có.
- `Services(...)` gom hai đối tượng vào `knowledge` và `assessments`. Bước này không đọc thêm dữ liệu và không chạy đánh giá.
- `create_app(...)` gắn chúng vào `api.state.services` và đăng ký routes. Vì đã truyền `services`, factory không gọi `build_services` thêm lần nữa. Tạo app chưa tự mở server HTTP.

## Khi chạy server và khi nhận request

```bash
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Uvicorn gọi `create_app()`. Factory đọc `KNOWLEDGE_PATH`/`DATABASE_PATH` hoặc đường dẫn mặc định qua `Settings.from_env()`, rồi gọi `build_services(settings)` vì chưa được truyền `services`. Các đối tượng được tạo một lần cho mỗi app instance; khi dùng nhiều workers, mỗi worker có app instance riêng.

Khi client gọi pipeline, FastAPI dùng `get_services(request)` trong `app/api/dependencies.py` để lấy chính `request.app.state.services`:

```python
# Đây là phần xử lý cốt lõi của route pipeline, sau khi request đã được parse.
response = evaluate(request, services.knowledge)
saved = services.assessments.save(request, response)
```

Workflow dùng knowledge để chạy bước 5–7; adapter database ghi output vào SQLite. Khởi tạo và nhận request là hai thời điểm khác nhau.

Demo đầy đủ đọc input mẫu, chạy bước 5–7, lưu và đọc lại kết quả:

```bash
python -m scripts.demo_bootstrap
```

Demo dùng SQLite trong thư mục tạm và dọn nó sau khi chạy. Nó in số bảng/criterion đã nạp, xác nhận API dùng lại cùng đối tượng và kiểm tra kết quả đọc từ DB bằng output workflow. Source: `scripts/demo_bootstrap.py`.

## Tên folder theo mục đích

| Tên trước | Tên hiện tại | Đặt code gì ở đây? |
|---|---|---|
| `app/modules/` | `app/business_modules/` | Nghiệp vụ theo BRD: xét criterion, tổng hợp requirement, risk, recommendation… |
| `app/application/` | `app/workflows/` | Điều phối thứ tự gọi modules và kiểm tra dữ liệu giữa các bước |
| `app/application/ports/` | `app/workflows/interfaces/` | Định nghĩa khả năng cần có, như đọc knowledge hoặc lưu assessment; chưa thực hiện kết nối |
| `app/core/` | `app/shared/` | Settings, tạo ID, errors và validation dùng chung |
| `app/infrastructure/` | `app/adapters/` | Code thực hiện kết nối file/DB/model/provider cụ thể |
| `infrastructure/knowledge/` | `adapters/knowledge_sources/` | Đọc knowledge từ JSON hiện tại hoặc nguồn DB sau này |
| `infrastructure/persistence/` | `adapters/database/` | Lưu và truy vấn dữ liệu runtime trong DB |
| `infrastructure/documents/` | `adapters/document_readers/` | Đọc nguồn tài liệu, PDF/DOCX và OCR |
| `infrastructure/retrieval/` | `adapters/search_backends/` | Kết nối công cụ full-text/vector search và reranker |
| `infrastructure/llm/` | `adapters/llm_providers/` | Gọi nhà cung cấp LLM |
| `infrastructure/authorization/` | `adapters/access_control/` | Kiểm tra quyền truy cập và hành động |
| `infrastructure/observability/` | `adapters/logs_and_audit/` | Ghi logs, traces, metrics và lịch sử gọi model |
| `infrastructure/reporting/` | `adapters/report_output/` | Lưu/xuất báo cáo PDF/JSON |

`api/` giữ xử lý HTTP; `contracts/` giữ cấu trúc dữ liệu C01–C13/X01/X02. Hai tên này được giữ vì đã mô tả trực tiếp trách nhiệm. Modules con giữ tên theo BRD; `business_modules/compliance_reasoning/interfaces.py` định nghĩa interface provider cho reasoning.

Ví dụ: `business_modules/retrieval` quyết định tìm evidence nào và chọn theo policy nào; `adapters/search_backends` thực hiện truy vấn công cụ tìm kiếm cụ thể. `workflows` ghép kết quả retrieval vào đầu vào reasoning. `bootstrap.py` là nơi chọn các implementations sẽ được sử dụng khi chúng được tích hợp.

Hiện `build_services` chỉ khởi tạo knowledge và SQLite. Các folder cho LLM/OCR/search/access/report vẫn là skeleton, chưa tự hoạt động khi đổi tên.
