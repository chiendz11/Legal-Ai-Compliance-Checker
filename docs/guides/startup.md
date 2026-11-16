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
5. `CachedHttpSourceStorage` được tạo với cấu hình local; constructor không tải PDF hoặc tạo folder cache. Xem [cách dùng cho nhóm A](../architecture/data_flow_and_storage.md).
6. `Services` gom các dependencies, có `llm_audit` và `source_storage` để inject vào service của từng module. Các module không tự lấy environment/secret trong engine.
7. `create_app` gắn Services vào app và đăng ký routes. Đây chưa phải chạy HTTP server.

```bash
python -m scripts.local_db init
python -m scripts.local_db seed
uvicorn legal_checker.main:create_app --factory --host 127.0.0.1 --port 8000
```

Chạy `python -m scripts.local_db init` để Alembic cập nhật schema trước app; dùng `seed` để nạp workbook. API không tự chạy migration, nạp Excel hoặc duyệt knowledge. [Hướng dẫn Alembic](../database/migrations.md).
Khi không chỉ định hash, reader capture source tables hiện tại vào snapshot dev bất biến.
Muốn replay snapshot cũ, export `KNOWLEDGE_SNAPSHOT_SHA256` bằng hash đã có trong DB.
Đổi source tables không thay nội dung reader đang dùng; khởi tạo reader mới để capture thay đổi.

Các POST chạy riêng bước 5–7 đã bỏ. API khởi chạy assessment toàn bộ đã có (`POST /api/v1/cases/{ca_id}/runs`, nhóm D); khi chưa có module bước 1–7, run kết thúc FAILED với `MODULE_NOT_IMPLEMENTED`.
GET full run/status/results dùng RunRepository và workflow_runs; Store chỉ dành standalone nhóm C. Bước 5–7 đã có engines; verifier theo criterion và quality vẫn là công việc riêng.
Factory có thể nhận `Services(knowledge, memory_store)` trong unit tests để thay writer.

`build_services()` cũng tạo case/run/report repositories, `AssessmentRunner` và hàng đợi (`ASSESSMENT_QUEUE=inline|celery`). PDF text/BM25/LLM adapter/review đã có; OCR/DOCX và verifier nghiệp vụ chưa mặc nhiên hoàn thành. ASSESSMENT_MODULES mặc định none, cần chọn modules rõ ràng để chạy thật.
Xem [DB local](../database/local_setup.md) và [hướng dẫn nhóm](../huong_dan_trien_khai_module_sau_seed.md).

## Chọn nguồn và inject verification

ASSESSMENT_MODULES=modules đọc upload/cache/HTTP thật. Chỉ DEV/EVAL mới chọn
modules_di_reference hoặc reference. LLM offline không gọi provider, không tự kết luận.
Document Intelligence mặc định dùng `DOCUMENTS_EXTRACTOR=rules`; nếu muốn bật trích xuất
semantic local cho 9 facts C02 bằng Ollama/Qwen (`DERIVED_REVIEW_PENDING`, ghi X02 `OLLAMA_LOCAL`),
cấu hình `DOCUMENTS_EXTRACTOR=hybrid` theo [documents_local_llm.md](../modules/documents_local_llm.md)
(tách biệt hoàn toàn với `ASSESSMENT_LLM` của C07).
Người 4 cung cấp CriterionVerificationProvider, người 2/4 cung cấp EvidenceRegistryProvider
cho chứng từ ngoài khi có; người 5 inject qua build_services(...). Registry và verifier
phải pin đúng context của run, không bật human_verified/verified chỉ vì DTO hợp lệ.
Ví dụ và chính sách tại [INTEGRATION_V1](../contracts/integration_spec.md).
