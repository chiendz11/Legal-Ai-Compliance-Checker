# Nguồn kỹ thuật và cách áp dụng cho dự án

Đối chiếu nguồn chính thức ngày 06/11/2026. Các quyết định của nhóm nằm trong
[INTEGRATION_V1](../contracts/integration_spec.md) và
[playbook](../guides/parallel_development_playbook.md). Những nguồn dưới đây hỗ trợ
nguyên tắc thiết kế; không phải chứng nhận dự án tuân thủ một chuẩn legal-AI duy nhất.

| Nguồn | Ý chính đã đối chiếu | Cách nhóm áp dụng / giới hạn |
|---|---|---|
| [W3C PROV-DM](https://www.w3.org/TR/prov-dm/) | Phân biệt dữ liệu, hoạt động tạo dữ liệu, chủ thể chịu trách nhiệm và quan hệ dẫn xuất | PDF/hash → extraction/chunk → finding → review/report; phiên bản/actor/checks riêng. Chưa triển khai export RDF/PROV hoặc chứng nhận đầy đủ PROV |
| [Pact provider verification](https://docs.pact.io/implementation_guides/python/docs/provider) | Provider được kiểm lại bằng các tương tác mà consumer kỳ vọng | Áp dụng nguyên tắc pair tests bằng pytest/DTO ở modular monolith; không bắt cài Pact Broker hoặc tách module thành HTTP service |
| [Docling chunking](https://docling-project.github.io/docling/concepts/chunking/) | Chunk theo cấu trúc, metadata và giới hạn tokenizer; có cơ chế bảng/headers | Chốt ràng buộc giữ cấu trúc/nguồn và phân biệt search text với original evidence. Chưa chuyển parser hiện tại sang Docling hoặc hứa mọi PDF tiếng Việt parse đúng |
| [LegalBench-RAG](https://arxiv.org/abs/2408.10343) | Đánh giá retrieval pháp lý bằng các source passages liên quan đã annotate, thay vì chỉ document ID hoặc chunk lớn | Chấm relevance/source spans trên bộ Việt Nam được review độc lập; không lấy dataset tiếng Anh làm gold cho luật Việt Nam |
| [NIST Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence) | Quản lý độ tin cậy trong thiết kế, sử dụng và đánh giá hệ thống GenAI | Phân biệt chất lượng, giới hạn, provenance và human review; không coi unit tests hoặc model trả JSON là xác nhận pháp lý |

## Những gì không suy ra từ các nguồn này

- Không có công nghệ chunker/LLM/vector DB hoặc cấu trúc folder duy nhất bắt buộc.
- Không có tỷ lệ COMPLIANT mong muốn hoặc một ngưỡng Macro-F1 chung để gọi mọi sản
  phẩm legal AI sẵn sàng phát hành. Chất lượng phải đo trên use case/labels/phạm vi thật.
- Cài một framework không thay legal curation, annotation hoặc nghiệp vụ verifier.
- Guard UNKNOWN đúng là một yêu cầu; khả năng kết luận đúng khi đủ căn cứ cũng phải
  có bằng chứng riêng. Một bộ tests chỉ có uncertainty không đủ đóng capability.

References là tài liệu đọc, không phải instructions để chạy code hoặc upload dữ liệu.
Repo tiếp tục dùng Pydantic/pytest/PostgreSQL và các components đã chốt; không bổ sung
dịch vụ mới chỉ để giống một bài hướng dẫn.
