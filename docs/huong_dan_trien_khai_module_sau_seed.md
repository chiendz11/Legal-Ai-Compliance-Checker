# Hướng dẫn Phát triển Module (Đã tái cấu trúc)

> [!NOTE]
> Tài liệu này đã được tách nhỏ thành các hướng dẫn chuyên biệt theo từng nhóm và module phát triển trong thư mục [`docs/modules/`](modules/):

### Danh mục tài liệu theo từng nhóm:
1. **[Quy chuẩn chung & Quy tắc JOIN Database](modules/README.md)**: Thiết kế module, chia sẻ connection, transaction và 3 lớp kiểm thử.
2. **[Nhóm A (Bước 1–2: Document Intelligence)](modules/group_a_document_intelligence.md)**: Tiếp nhận PDF/DOCX, trích xuất metadata, chunking và trích dẫn.
3. **[Nhóm B (Bước 3–4: Legal Scope, Citation & Retrieval)](modules/group_b_legal_and_retrieval.md)**: Phạm vi áp dụng (C04), hiệu lực thời gian (C05), kiểm định trích dẫn (C09) và truy xuất Top-K (C06).
4. **[Nhóm C (Bước 5–7: Compliance, Risk & Recommendation)](modules/group_c_compliance_and_risk.md)**: Đánh giá tiêu chí (C07/C08), tổng hợp rủi ro (C10) và khuyến nghị xử lý (C11).
5. **[Nhóm D (Bước 8–9: Report & UI/Frontend)](modules/group_d_report_and_frontend.md)**: Tổng hợp báo cáo hai nhánh (C13), sự kiện review (C12) và giao diện.
