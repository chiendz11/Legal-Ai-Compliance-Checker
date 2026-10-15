# Tài liệu cho nhóm phát triển

Bắt đầu theo thứ tự:

1. [Tạo/kích hoạt môi trường ảo và cài dependencies](dev_setup.md).
2. [Tải dataset DEV_VALIDATION](dataset_download.md).
3. [Tạo PostgreSQL local và seed](local_database.md).
4. [Triển khai từng nhóm, query/JOIN và bàn giao](huong_dan_trien_khai_module_sau_seed.md).
5. [Kiến trúc và trạng thái skeleton](architecture.md), [khởi tạo](startup.md), [ghép module](module_integration.md).
6. [Các script, lệnh và trạng thái sử dụng](../scripts/README.md).

| Tài liệu | Mục đích |
|---|---|
| [BRD v1.1](BRD_v1.1.pdf) | Yêu cầu nghiệp vụ gốc |
| [Contracts gốc](data_contracts_v7_3_2.md) | Baseline thiết kế C01–C13/X01/X02 |
| [Giải thích contracts](contracts_va_muc_dich_vi.md) · [PDF](contracts_va_muc_dich_vi.pdf) | Mục đích, input/output, producer/consumer và hiện trạng code |
| [Contracts máy đọc được](contracts/README.md) · [Catalog](contracts/catalog.json) | C01–C13/X01/X02 riêng, producer/consumer, quy tắc và mapping DB |
| [OpenAPI thiết kế UI](openapi.design.json) | Contract để mock/triển khai UI, có phân biệt trạng thái; schema thực tế xem tại `/openapi.json` của backend đang chạy |
| [Module schemas](module_contracts.schema.json) · [DB catalog](contracts/database_catalog.json) | Handoff input/output và tên/cột/khóa SQL cho repository/mapper |
| [LLM audit dùng chung](llm_audit.md) · [schema X02](llm_audit.schema.json) | Quy ước ghi log DB cho các client LLM riêng của module |
| [Đọc PDF và cache local](source_storage.md) | Nhóm A đọc nguồn HTTP(S), kiểm tra SHA-256 và đưa bytes vào parser/OCR |
| [Alembic và schema DB](database_migrations.md) | Tiếp nhận DB cũ, tạo/chạy revisions và phân biệt migration với seed |
| [Dataset structured r2](v750_source_pdf360_r2_structured.md) | Các gói, provenance/chunking, split và giới hạn của references |

Dataset hiện tại: v7.5.0-source-pdf360-r2-structured / supabase-public-v1, DEV_VALIDATION 240 DEV + 60 VALIDATION. Bước 5–7 chỉ còn skeleton nội bộ, không có HTTP POST riêng. PDF/Excel/DB được lưu ngoài Git; code tải/seed và tài liệu được versioned cùng repo.

Các hướng dẫn release cũ đã xóa; không dùng run IDs hoặc seed paths của chúng cho bản hiện tại. BRD/contracts gốc được giữ nguyên. File khóa tạm của trình soạn thảo không phải tài liệu và không commit.
