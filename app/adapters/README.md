# Kết nối dữ liệu và dịch vụ kỹ thuật

Các thư mục này chứa implementations kết nối với storage, tài liệu, model/provider và các cơ chế kỹ thuật khác. Nghiệp vụ vẫn nằm trong `app/business_modules/`; workflow ở `app/workflows/`; input/output schemas ở `app/contracts/`.

| Folder | Mục đích | Trạng thái hiện tại |
|---|---|---|
| `knowledge_sources/` | Đọc knowledge từ nguồn lưu trữ, kiểm tra schema/checksum, lập index requirement/criterion/rule/legal basis để module nghiệp vụ tra cứu | `snapshot.py` đã chạy, đọc `data/knowledge.json`; sau này có thể thêm nguồn DB |
| `database/` | Ghi/đọc kết quả case/run, snapshots, evidence và audit trong transaction; quản lý idempotency và deployment pin | `sqlite.py` đã chạy với SQLite MVP |
| `document_readers/` | Đọc nguồn file/object storage, PDF/DOCX/OCR; giữ source hash, trang, text và readability để Document Intelligence tạo profile/chunks/citations | Skeleton; interfaces `SourceStorage`/`DocumentReader` |
| `search_backends/` | Kết nối full-text/vector index và reranker; trả candidate IDs/scores/index version phục vụ evidence retrieval | Skeleton; interfaces `EvidenceIndex`/`EvidenceReranker` |
| `llm_providers/` | Gọi provider để đề xuất finding/giải thích/quotes theo structured schema; xử lý transport, timeout và provider errors | Skeleton; interface `CriterionProposalProvider` |
| `access_control/` | Kiểm tra actor có quyền xem case/tenant, review kết quả hoặc phát hành knowledge snapshot | Skeleton; interface `AccessPolicy`, chưa nối API |
| `logs_and_audit/` | Ghi trace/log/metrics và X02 audit cho lời gọi LLM thực tế: model/prompt/schema, hashes, usage, latency, lỗi | Skeleton; interface `LlmAuditSink` |
| `report_output/` | Lưu phiên bản báo cáo và xuất artifacts PDF/JSON qua adapters, giữ case/snapshot và phân tách các nhánh kết quả | Skeleton; interfaces `ReportStore`/`ReportExporter` |

## Phân công giữa nghiệp vụ và adapters

- `business_modules/retrieval` chọn query, criterion và policy evidence; `adapters/search_backends` thực hiện tìm kiếm/xếp hạng qua index/model cụ thể. Retrieval miss không tạo legal finding.
- `business_modules/compliance_reasoning` quyết định gates và finding được chấp nhận; `adapters/llm_providers` cung cấp proposal. Provider không xác nhận thay backend các cờ source/scope/coverage/absence.
- `business_modules/document_intelligence` tạo C02/C03 và chunks; `adapters/document_readers` đọc file và text/OCR, giữ vị trí nguồn.
- `business_modules/reporting` xây nội dung C13 và workflow phát hành; `adapters/report_output` lưu/export artifacts. Adapter không tự xác nhận human review hay publish authorization.
- `access_control` kiểm tra quyền hành động; authentication xác định actor là ai và cần được nối từ identity provider khi triển khai. Hiện API chưa có production authentication/authorization.
- `logs_and_audit` chứa cơ chế ghi audit/telemetry. Case/run audit đang chạy hiện được lưu bởi adapter SQLite trong `database`; folder logs_and_audit chưa có implementation riêng.

`app/bootstrap.py` khởi tạo adapters hiện có: `Knowledge` đọc file JSON và đáp ứng interface `KnowledgeSnapshot`; `Store` chuẩn bị SQLite và đáp ứng interface `AssessmentStore`. Business modules sử dụng interfaces để có thể thay JSON/SQLite bằng adapters khác mà giữ nguyên contracts và rule nghiệp vụ. Xem [ví dụ khởi tạo chạy được](../../docs/startup.md).

Skeleton folders có README/namespace để xác định điểm đặt implementation. Chúng chưa tự cung cấp OCR, vector search, provider LLM, phân quyền, telemetry hay xuất báo cáo.
