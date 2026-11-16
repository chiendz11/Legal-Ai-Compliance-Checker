# Tài liệu Dự án Legal AI Compliance Checker

[Gold Master thống nhất — 16/11, R12](guides/gold_master_20261114.md):
một nguồn đáp án nhiều lớp bằng SQLite/JSON, cùng bản Excel để đọc.
220 ca đã biên soạn theo phạm vi catalog/draft và evidence pool công bố; 140 ca còn
chờ chấm. Scoped được nhập đúng phạm vi, không biến thành đáp án E2E;
`full_e2e_gold_ready=false`. [Checkpoint trước](guides/e2e_gold_reauthored_20261114.md).

[Dataset PDF360 v4 r2, runtime và knowledge đã duyệt — 10/11](guides/dataset_pdf360_v4r2_runtime_20261110.md):
baseline hiện hành cho DB mới, 360 PDF cùng nguồn, snapshot chủ dự án đã duyệt;
phân biệt literal reference độc lập với output engine SILVER. Các biên bản bên dưới
miêu tả kết quả và giới hạn tại thời điểm của từng đợt.

[Nghiệm thu baseline v4 r2 và demo — 10/11](guides/baseline_v4_acceptance_20261110.md):
run HD360_001, kiểm 90 baseline, sửa tên bên bán/tài khoản và giới hạn gói nguồn
so với dataset runtime đang dùng để seed.

[Baseline PDF v4 và mặc định dân sự — 09/11](guides/baseline_v4_civil_defaults_20261109.md):
sửa evidence bàn giao, phạm vi Điều 453, bổ sung mốc điều kiện giao dịch chung trong
PDF synthetic và phân biệt gói nguồn với workbook runtime dùng seed.

[Chuẩn hóa báo cáo và tối ưu LLM — 09/11](guides/report_consistency_and_llm_efficiency_20261109.md):
coverage, trạng thái, C11 bindings và shared-source batching.

[Demo E2E và rà báo cáo mới — 09/11](guides/e2e_source_context_results_20261109.md):
run thật trên k3d, tám tab/export/lineage, kết quả và các điểm hiển thị còn cần cải thiện.

[Thử nghiệm phương pháp xử lý hợp đồng — 09/11](guides/legal_document_methods_trial_20261109.md):
chunk theo cấu trúc/câu, citation từ source spans, mở ngữ cảnh có giới hạn và bỏ recipe GTC tự đề xuất SATISFIED.

[Sửa viện dẫn và điều kiện giao dịch chung — 09/11](guides/citation_and_general_terms_fix_20261109.md): extraction qua ranh giới chunk, định danh C09 V2 và evidence nội quy/hiệu lực.

[Hoàn thiện các điểm còn thiếu trong dự thảo — 09/11](guides/remaining_verification_alignment_20261109.md): điều kiện phát sinh, mẫu số bảo trì, trọng tài và mốc C01 → C05; có kết quả demo riêng.

[Rà soát baseline v3 theo chế độ dự thảo — 09/11](guides/baseline_v3_draft_review_fix_20261109.md):
C01/API, verifier, diện tích sàn, phạm vi đánh giá và cách nâng cấp DB.

> Trung tâm tài liệu kỹ thuật, kiến trúc, quy chuẩn dữ liệu và hướng dẫn triển khai hệ thống kiểm tra tuân thủ pháp lý hợp đồng mua bán căn hộ bằng AI.

---

## 🚀 Hướng dẫn Bắt đầu Nhanh (Onboarding)

**[Chứng từ synthetic và sửa inference — 07/11](guides/synthetic_evidence_and_inference_fixes_20261107.md)**: chế độ đồ án gắn source/hash, verifier, extraction bảo hành, batch LLM và quote IDs.

Dành cho thành viên mới hoặc thiết lập môi trường phát triển từ đầu:

**[Demo TEAM trên k3d — HD360_001.pdf](guides/demo_team_k3d_results_20261107.md)**:
run thật qua UI/queue/modules/LLM, so sánh report cũ, kiểm handoff và các nút chặn
verifier/budget/quote còn lại. [Runbook chuyển dataset trong cụm](guides/demo_team_k3d_20261107.md).

**[Biên bản thống nhất docs cho năm người — 07/11](guides/docs_alignment_changes_20261107.md)**:
14 điểm đã sửa, ownership, cách nối hàm, nguồn dữ liệu live, gates và phần implementation
còn cần nghiệm thu. Dùng cùng playbook hiện hành; không lấy trạng thái kế hoạch theo
tuần hoặc PDF contracts lịch sử làm contract code mới.

**[Dataset TEAM_BASELINE_20261107](guides/dataset_team_baseline_20261107.md)**:
knowledge/runtime/QA cùng snapshot, 36 yêu cầu tham chiếu mỗi ca, cách cài ZIP và
seed DB local mới của đợt 07/11. Đã được thay bởi [release PDF360 v4 r2](guides/dataset_pdf360_v4r2_runtime_20261110.md).

**[Sổ tay triển khai song song cho năm người](guides/parallel_development_playbook.md)**: quyết định đã chốt, input/output, owner, proof obligations và bộ ca nghiệm thu. Đọc trước khi chia task.

**[Changelog tích hợp và việc đã sửa](guides/integration_alignment_changes_20261105.md)**: rà soát snapshot, quyết định kiến trúc, thay đổi code/contracts, kết quả kiểm tra và backlog năm người.

**[Revision tri thức 06/11](guides/knowledge_alignment_changes_20261106.md)** và **[policy scope/temporal](contracts/knowledge_applicability_policy.md)**: chốt tên dữ kiện, mốc chọn phiên bản, nguồn và chuyển tiếp từ workbook reviewed; phân biệt knowledge revision với baseline runtime/eval cũ.

**[Bàn giao main và việc cần làm cho 5 người](guides/team_onboarding_and_next_steps.md)**: lấy code, cài ZIP baseline, giữ DB cũ và backlog tích hợp có owner.

1. **[Cài đặt Môi trường Phát triển](guides/dev_setup.md)**: Thiết lập Python virtualenv (`.venv`), công cụ linter (`ruff`), test suite (`pytest`).
2. **[Tải & Chuẩn bị Dataset](database/dataset_and_corpus.md)**: Tải bộ dữ liệu mẫu DEV_VALIDATION (240 DEV / 60 VAL).
3. **[Khởi tạo PostgreSQL & Seed Dữ liệu](database/local_setup.md)**: Dựng cơ sở dữ liệu PostgreSQL local và seed tri thức pháp luật.
4. **[Khởi chạy Backend & CLI](guides/startup.md)**: Hướng dẫn chạy server FastAPI và các lệnh kiểm tra.
5. **[Quy chuẩn & Hướng dẫn Module](modules/README.md)**: Quy tắc chia sẻ kết nối, khóa JOIN và ba lớp kiểm thử.

---

## 📚 Bản đồ Tài liệu (Documentation Sitemap)

### 1. Yêu cầu Nghiệp vụ (`business/`)
* **[Kế hoạch Triển khai 10 Tuần (W4–W13)](business/roadmap_10_weeks.md)** ([Bản Excel XLSX](business/ke_hoach_10_tuan.xlsx) · [Bản CSV](business/ke_hoach_10_tuan.csv)): Phân công trách nhiệm 5 workstreams, lộ trình 3 giai đoạn và tiêu chuẩn hoàn thành (Definition of Done).
* **[Báo cáo Tiến độ Tuần 9 (PPTX)](business/bao_cao_tien_do_tuan_9.pptx)** ([Thư mục Slides](business/slides/bao_cao_tien_do_tuan_9.pptx)): Bản trình chiếu tiến độ/mục tiêu Tuần 9; các tỷ lệ kỳ vọng không thay bằng chứng nghiệm thu (Cột mốc First Working Inference E2E, Cụm K3d GitOps, Async Task Queue và Reviewer Workbench).
* **[Báo cáo Tuần 10 điều chỉnh](business/bao_cao_tien_do_tuan_10.md)** ([PPTX](business/slides/bao_cao_tien_do_tuan_10.pptx), [PDF](business/slides/bao_cao_tien_do_tuan_10.pdf)): Bám workbook kế hoạch: Inference MVP, phần việc năm người, smoke/regression trên DEV, nguồn của kết luận và danh sách lỗi ưu tiên.
* **[Báo cáo Tuần 11 — kế hoạch và thực tế](business/bao_cao_tien_do_tuan_11.md)** ([PPTX](business/slides/bao_cao_tien_do_tuan_11.pptx), [PDF](business/slides/bao_cao_tien_do_tuan_11.pdf)): Đối chiếu nhiệm vụ năm người, bằng chứng hiện có và các bước còn lại để nghiệm thu Inference STABLE.
* **[Mục lục và trạng thái các slide](business/slides/README.md)**: Phân biệt báo cáo tuần đã điều chỉnh với bản nháp lịch sử về tri thức/công nghệ/Gold có nhận định chưa nghiệm thu.
* **[Business Requirements Document (BRD v1.1)](business/BRD_v1.1.pdf)**: Đặc tả yêu cầu nghiệp vụ gốc, quy tắc thẩm định pháp lý và xử lý trường hợp bất định.

### 2. Kiến trúc & Thiết kế Kỹ thuật (`architecture/`)
* **[Kiến trúc Tổng thể Hệ thống](architecture/system_architecture.md)**: Mô hình thành phần, luồng xử lý hai nhánh (Legal Scope vs Citation Validation), quy chuẩn CI/CD và ranh giới hệ thống.
* **[Luồng Dữ liệu & Lưu trữ PDF](architecture/data_flow_and_storage.md)**: Cơ chế đọc file PDF/DOCX từ HTTP(S), kiểm tra SHA-256 và cache cục bộ.
* **[Bản Thiết kế OpenAPI](architecture/openapi.design.json)**: Đặc tả 26 operations API RESTful đã có handler cho frontend và backend.

### 3. Quy chuẩn Hợp đồng Dữ liệu (`contracts/`)
* **[Đặc tả tích hợp INTEGRATION_V1](contracts/integration_spec.md)**: quyết định chung, H01–H24, owner năm người, nguồn live/reference và policy review.
* **[Từ điển fields/facts và ma trận criterion](contracts/data_dictionary.md)**: canonical names/units, source/owner và lệnh audit read-only.
* **[Hướng dẫn Data Contracts C01–C13 & X01–X02](contracts/README.md)**: Giải thích chi tiết mục đích, producer, consumer và ngữ nghĩa từng hợp đồng.
* **[Catalog Contracts](contracts/catalog.json)**: Danh mục máy đọc được (machine-readable) ánh xạ từng Contract ID sang Pydantic Model.
* **[Database Catalog](contracts/database_catalog.json)**: 50 bảng workbook + 6 QA, 78 FK workbook và danh mục bảng vận hành bổ sung; Alembic là nguồn schema thật.
* **[JSON Schemas](contracts/)**: Bộ schema JSON Schema Draft 2020-12 cho từng hợp đồng dữ liệu.

### 4. Cơ sở Dữ liệu & Tri thức Pháp luật (`database/`)
* **[Cài đặt & Seed PostgreSQL Local](database/local_setup.md)**: Dựng database phát triển, nạp tri thức pháp lý và dữ liệu mẫu.
* **[Quản lý Migrations với Alembic](database/migrations.md)**: Hướng dẫn tạo và chạy Alembic migrations khi sửa đổi cấu trúc bảng.
* **[Cập nhật Workbook Reviewed vào DB đang có](database/reviewed_dataset_update.md)**: Lệnh dry-run/update, giữ hợp đồng upload, snapshot, run/report và hướng dẫn thay ZIP trên Drive.
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

- [Sửa verifier/evidence HD360_001 ngày 08/11](guides/hd360_followup_verification_20261108.md): full review, C06 refinement và cách đọc NOT_TRIGGERED.

- [Xử lý nốt 12 trường hợp HD360_001](guides/complete_runtime_alignment_20261108.md): catalog revision, nguồn COMPLETE_R4 và trạng thái không phát sinh.
