# Tài liệu Dự án Legal AI Compliance Checker

> Trung tâm tài liệu kỹ thuật, kiến trúc, quy chuẩn dữ liệu và hướng dẫn triển khai hệ thống kiểm tra tuân thủ pháp lý hợp đồng mua bán căn hộ bằng AI.

---

## 🚀 Hướng dẫn Bắt đầu Nhanh (Onboarding)

Dành cho thành viên mới hoặc thiết lập môi trường phát triển từ đầu:

1. **[Cài đặt Môi trường Phát triển](guides/dev_setup.md)**: Thiết lập Python virtualenv (`.venv`), công cụ linter (`ruff`), test suite (`pytest`).
2. **[Tải & Chuẩn bị Dataset](database/dataset_and_corpus.md)**: Tải bộ dữ liệu mẫu DEV_VALIDATION (240 DEV / 60 VAL).
3. **[Khởi tạo PostgreSQL & Seed Dữ liệu](database/local_setup.md)**: Dựng cơ sở dữ liệu PostgreSQL local và seed tri thức pháp luật.
4. **[Khởi chạy Backend & CLI](guides/startup.md)**: Hướng dẫn chạy server FastAPI và các lệnh kiểm tra.
5. **[Quy chuẩn & Hướng dẫn Module](modules/README.md)**: Quy tắc chia sẻ kết nối, khóa JOIN và ba lớp kiểm thử.

---

## 📚 Bản đồ Tài liệu (Documentation Sitemap)

### 1. Yêu cầu Nghiệp vụ (`business/`)
* **[Kế hoạch Triển khai 10 Tuần (W4–W13)](business/roadmap_10_weeks.md)** ([Bản Excel XLSX](business/ke_hoach_10_tuan.xlsx) · [Bản CSV](business/ke_hoach_10_tuan.csv)): Phân công trách nhiệm 5 workstreams, lộ trình 3 giai đoạn và tiêu chuẩn hoàn thành (Definition of Done).
* **[Business Requirements Document (BRD v1.1)](business/BRD_v1.1.pdf)**: Đặc tả yêu cầu nghiệp vụ gốc, quy tắc thẩm định pháp lý và xử lý trường hợp bất định.

### 2. Kiến trúc & Thiết kế Kỹ thuật (`architecture/`)
* **[Kiến trúc Tổng thể Hệ thống](architecture/system_architecture.md)**: Mô hình thành phần, luồng xử lý hai nhánh (Legal Scope vs Citation Validation), quy chuẩn CI/CD và ranh giới hệ thống.
* **[Luồng Dữ liệu & Lưu trữ PDF](architecture/data_flow_and_storage.md)**: Cơ chế đọc file PDF/DOCX từ HTTP(S), kiểm tra SHA-256 và cache cục bộ.
* **[Bản Thiết kế OpenAPI](architecture/openapi.design.json)**: Đặc tả 20 operations API RESTful đề xuất cho frontend và backend.

### 3. Quy chuẩn Hợp đồng Dữ liệu (`contracts/`)
* **[Hướng dẫn Data Contracts C01–C13 & X01–X02](contracts/README.md)**: Giải thích chi tiết mục đích, producer, consumer và ngữ nghĩa từng hợp đồng.
* **[Catalog Contracts](contracts/catalog.json)**: Danh mục máy đọc được (machine-readable) ánh xạ từng Contract ID sang Pydantic Model.
* **[Database Catalog](contracts/database_catalog.json)**: Cấu trúc 56 bảng PostgreSQL và 78 khóa ngoại (Foreign Keys).
* **[JSON Schemas](contracts/)**: Bộ schema JSON Schema Draft 2020-12 cho từng hợp đồng dữ liệu.

### 4. Cơ sở Dữ liệu & Tri thức Pháp luật (`database/`)
* **[Cài đặt & Seed PostgreSQL Local](database/local_setup.md)**: Dựng database phát triển, nạp tri thức pháp lý và dữ liệu mẫu.
* **[Quản lý Migrations với Alembic](database/migrations.md)**: Hướng dẫn tạo và chạy Alembic migrations khi sửa đổi cấu trúc bảng.
* **[Tải Dataset & Thông số Corpus](database/dataset_and_corpus.md)**: Cấu trúc tập dữ liệu v7.5.0, provenance và phân chia DEV / VALIDATION.

### 5. Hướng dẫn Lập trình viên (`guides/`)
* **[Thiết lập Môi trường Cục bộ](guides/dev_setup.md)**: Hướng dẫn cài đặt Python 3.11+, biến môi trường và dependencies.
* **[Khởi chạy Dịch vụ & CLI](guides/startup.md)**: Lệnh chạy server uvicorn, CLI migration/seed và kiểm tra sức khỏe.
* **[Tích hợp Audit LLM Dùng chung](guides/llm_audit.md)**: Quy chuẩn ghi log các lần gọi mô hình ngôn ngữ lớn (X02).

### 6. Hướng dẫn Phát triển theo Module (`modules/`)
* **[Quy chuẩn Tích hợp Chung](modules/README.md)**: Nguyên tắc handoff, kết nối database, khóa JOIN và kiểm thử.
* **[Nhóm A (Bước 1–2: Document Intelligence)](modules/group_a_document_intelligence.md)**: Tiếp nhận hợp đồng, OCR/parser, trích xuất facts (C02) và citations (C03).
* **[Nhóm B (Bước 3–4: Legal Scope, Citation & Retrieval)](modules/group_b_legal_and_retrieval.md)**: Xác định phạm vi áp dụng (C04), hiệu lực thời gian (C05), kiểm định viện dẫn (C09) và truy xuất Top-K (C06).
* **[Nhóm C (Bước 5–7: Compliance, Risk & Recommendation)](modules/group_c_compliance_and_risk.md)**: Đánh giá tiêu chí (C07/C08), tổng hợp rủi ro (C10) và khuyến nghị xử lý (C11).
* **[Nhóm D (Bước 8–9: Report Aggregation & UI/Frontend)](modules/group_d_report_and_frontend.md)**: Hợp nhất hai nhánh, ghi nhận sự kiện review (C12) và xuất báo cáo (C13).
