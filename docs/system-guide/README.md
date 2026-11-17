# System Deep Dive — Hướng dẫn Chuyên sâu Hệ thống Legal AI Compliance Checker

> **Vai trò của bộ tài liệu này:** Giải thích *tại sao* hệ thống được thiết kế như hiện nay, *cách thuật toán vận hành*, *dữ liệu biến đổi qua từng contract C01–C13*, các *trade-off kỹ thuật*, và *ánh xạ trực tiếp tới class/function trong source code* bằng các tình huống thực tế của hợp đồng mua bán căn hộ tại Việt Nam.

---

## 0. Dùng bộ tài liệu này để thuyết trình

Mỗi chương (01–10) mở đầu bằng mục **“0. Trình bày nhanh”** — một câu tóm tắt, một hình dung đời thường, ba ý phải nói được, bảng thuật ngữ và số slide tương ứng — và kết thúc bằng mục **“Hỏi – đáp khi trình bày”** kèm các hiểu lầm hay gặp. Phần giữa giữ nguyên nội dung kỹ thuật chi tiết để tra cứu.

**Deck đi kèm:** [Công nghệ C01–C13 — PPTX](../business/slides/cong_nghe_va_ky_thuat_he_thong_c01_c13.pptx) · [PDF](../business/slides/cong_nghe_va_ky_thuat_he_thong_c01_c13.pdf) (44 slide, có ghi chú thuyết trình trên từng slide).

| Phần trong deck | Slide | Chương system-guide | Thời lượng gợi ý |
|---|---|---|---|
| Mở đầu & lộ trình | 1–2 | — | 1 phút |
| 1. Bài toán & kiến trúc | 3–9 | [01](01-system-overview-and-end-to-end-flow.md) | 6–8 phút |
| 2. Dữ liệu & kho tri thức | 10–13 | [02](02-knowledge-runtime-and-gold-master.md) | 4–5 phút |
| 3. Đọc hợp đồng | 14–18 | [03](03-document-intelligence.md) | 5–6 phút |
| 4. Luật nào áp dụng? | 19–23 | [04](04-scope-and-temporal-resolution.md) · [05 phần 1](05-citation-validation-and-retrieval.md) | 8–9 phút |
| 5. Tìm bằng chứng & kết luận | 24–30 | [05 phần 2](05-citation-validation-and-retrieval.md) · [06](06-compliance-reasoning-and-c07-c08.md) | 10–12 phút |
| 6. Báo cáo, con người & vận hành | 31–41 | [07](07-risk-and-recommendation.md) · [08](08-report-generation-and-human-review.md) · [09](09-async-workflow-and-job-lifecycle.md) · [10](10-unknown-insufficient-and-diagnostics.md) | 12–15 phút |
| Công nghệ, kết luận, hỏi đáp | 42–44 | — | 3 phút + hỏi đáp |

**Nếu chỉ có 15 phút:** trình bày các slide 4, 5, 8, 9, 20, 26, 27, 28, 34, 37, 39, 43 — đủ kể trọn câu chuyện “vì sao – luật nào – kết luận thế nào – ai duyệt – đọc `UNKNOWN` ra sao”.

### Bảng thuật ngữ chung (dùng xuyên suốt)

| Thuật ngữ | Nghĩa dễ hiểu | Chương |
|---|---|---|
| Contract `C01`–`C13` | Mẫu dữ liệu bàn giao giữa hai bước xử lý | 01 |
| Nhánh A / Nhánh B | A: luật thật sự áp dụng. B: luật mà hợp đồng tự viện dẫn | 01, 04, 05 |
| Snapshot / pin | Bản đóng băng tri thức có mã băm; lượt chạy ghi rõ dùng bản nào | 02 |
| Chunk | Đoạn nguyên văn của hợp đồng kèm trang và vị trí ký tự | 03 |
| Fact | Dữ kiện đã trích từ hợp đồng, có bằng chứng | 03 |
| Requirement family / criterion | Nhóm yêu cầu pháp lý / tiêu chí kiểm tra nhỏ nhất | 02, 04 |
| Kleene 3 giá trị | `MATCH` / `NO_MATCH` / `UNKNOWN` | 04 |
| Gates | 8 cờ kiểm chứng trước khi chốt kết luận | 06 |
| Finding | Nhãn mức tiêu chí: `SATISFIED`, `VIOLATED`, `MISSING`, `UNKNOWN` | 06, 10 |
| `INSUFFICIENT` | Trạng thái mức yêu cầu khi còn tiêu chí chưa biết | 06, 10 |
| `OUTSIDE_REVIEW_SCOPE` / `NOT_TRIGGERED` | Ngoài chế độ rà soát / nghĩa vụ không phát sinh — đều không phải “Đạt” | 06, 10 |
| X02 | Nhật ký mỗi lần gọi LLM (không lưu API key) | 01, 03, 07 |

---

## 1. Phân định ranh giới với tài liệu gốc hiện có

`docs/system-guide/` **không sao chép và không thay thế** các đặc tả chuẩn đang được duy trì trong repository. Khi cần tra cứu schema, SQL mẫu, quy trình nghiệm thu hoặc quy tắc triển khai theo module, hãy đọc trực tiếp tài liệu thẩm quyền tương ứng:

| Lớp tài liệu | Mục đích chính | Tài liệu thẩm quyền trong `docs/` |
|---|---|---|
| **Kiến trúc & Dữ liệu tổng quan** | Topology thành phần, luồng HTTP/worker, tải & cache PDF | [system_architecture.md](../architecture/system_architecture.md) · [data_flow_and_storage.md](../architecture/data_flow_and_storage.md) |
| **Contracts & Policy gốc** | Schema JSONDraft 2020-12, ownership C01–C13, `INTEGRATION_V1`, policy chọn luật | [contracts/README.md](../contracts/README.md) · [integration_spec.md](../contracts/integration_spec.md) · [knowledge_applicability_policy.md](../contracts/knowledge_applicability_policy.md) · [report_presentation.md](../contracts/report_presentation.md) |
| **Hướng dẫn Triển khai Module** | Input/output, SQL queries, quy tắc JOIN, kiểm thử bàn giao Nhóm A–D | [modules/README.md](../modules/README.md) · [Nhóm A](../modules/group_a_document_intelligence.md) · [Nhóm B](../modules/group_b_legal_and_retrieval.md) · [Nhóm C](../modules/group_c_compliance_and_risk.md) · [Nhóm D](../modules/group_d_report_and_frontend.md) |
| **Vận hành, DB & Gold** | Setup local, k3d/ArgoCD, kịch bản demo, Gold Master & coverage | [demo.md](../guides/demo.md) · [gold_master_20261114.md](../guides/gold_master_20261114.md) · [local_setup.md](../database/local_setup.md) · [local_k3d_argocd_cicd_framework.md](../devops/local_k3d_argocd_cicd_framework.md) |
| **Slide trình bày đồng hành** | Tóm tắt trực quan kiến trúc, thuật toán `C01–C13` & hiện trạng hệ thống | [Slide Công nghệ C01–C13 (đồng bộ Deep Dive)](../business/slides/cong_nghe_va_ky_thuat_he_thong_c01_c13.pptx) · [Slide Tổng quan Hệ thống 16/11/2026](../business/slides/Legal-AI-Compliance-Checker-bao-cao-he-thong-2026-11-16.pptx) |
| **System Deep Dive (Thư mục này)** | Cơ chế thuật toán, lý do thiết kế, trade-off, walkthrough dữ liệu và trỏ tới source code | Bộ 10 tài liệu bên dưới |

---

## 2. Mục lục 10 chủ đề Deep Dive

| STT | Tài liệu | Nội dung trọng tâm | Tài liệu gốc & Source code liên kết chính |
|---:|---|---|---|
| **01** | [01 — System Overview & End-to-End Flow](01-system-overview-and-end-to-end-flow.md) | Bài toán pháp lý căn hộ, hai nhánh độc lập (Legal Scope vs Citation Validation), kiến trúc Modular Monolith, walkthrough 1 hợp đồng qua C01–C13 | [system_architecture.md](../architecture/system_architecture.md) · [`assessment_workflow.py`](../../backend/src/legal_checker/workflows/assessment_workflow.py) |
| **02** | [02 — Knowledge, Runtime & Gold Master](02-knowledge-runtime-and-gold-master.md) | Tách biệt 3 miền dữ liệu (Knowledge / Runtime / QA-Gold), cơ chế Pinning (`DeploymentPin`, `Context`, `X01`), Gold Master R12 đa lớp và ranh giới đánh giá | [gold_master_20261114.md](../guides/gold_master_20261114.md) · [`legal_knowledge/`](../../backend/src/legal_checker/modules/legal_knowledge/models.py) · [`evaluator.py`](../../backend/src/legal_checker/modules/benchmarks/evaluator.py) |
| **03** | [03 — Document Intelligence](03-document-intelligence.md) | Intake kiểm SHA-256, `PdfTextReader`, thuật toán chunking giữ offset nguyên văn (`structural-sentences-v2`), rule extractor vs `SemanticDocumentExtractor` (Ollama local hoặc OpenAI API) và C03 | [group_a_document_intelligence.md](../modules/group_a_document_intelligence.md) · [documents_local_llm.md](../modules/documents_local_llm.md) · [`modules/documents/`](../../backend/src/legal_checker/modules/documents/service.py) |
| **04** | [04 — Scope & Temporal Resolution](04-scope-and-temporal-resolution.md) | Predicate Engine & **Kleene 3-valued logic**, `CAN_XAC_MINH_TU_CACH_CAC_BEN`, Marker Mapping, half-open interval `[hieu_luc_tu, hieu_luc_den)`, chuyển tiếp Luật 29/2023 & 43/2024 | [knowledge_applicability_policy.md](../contracts/knowledge_applicability_policy.md) · [`scope_resolver.py`](../../backend/src/legal_checker/modules/applicable_law/scope_resolver.py) · [`temporal_resolver.py`](../../backend/src/legal_checker/modules/applicable_law/temporal_resolver.py) |
| **05** | [05 — Citation Validation & Retrieval](05-citation-validation-and-retrieval.md) | Nhánh B C09 (Normalize → Identity → Temporal → Domain → Classify) và C06 `HybridRetrievalService` (BM25 + RRF + Anchors + Reranker) + Selective Full-Document Review | [group_b_legal_and_retrieval.md](../modules/group_b_legal_and_retrieval.md) · [`citation_validation/`](../../backend/src/legal_checker/modules/citation_validation/service.py) · [`retrieval/service.py`](../../backend/src/legal_checker/modules/retrieval/service.py) |
| **06** | [06 — Compliance Reasoning & C07/C08](06-compliance-reasoning-and-c07-c08.md) | Ranh giới `Observation` vs `Gates`, `DRAFT_CONTENT_REVIEW_V1` (`DRAFT_REVIEW` vs `FULL_TRANSACTION_EVALUATION`), kiểm toán số học `Decimal`, tổng hợp `AGG_CAN_HO_V1` và Disposition | [group_c_compliance_and_risk.md](../modules/group_c_compliance_and_risk.md) · [`criterion_reasoner.py`](../../backend/src/legal_checker/modules/compliance/criterion_reasoner.py) · [`requirement_aggregator.py`](../../backend/src/legal_checker/modules/compliance/requirement_aggregator.py) |
| **07** | [07 — Risk & Recommendation](07-risk-and-recommendation.md) | Hợp nhất rủi ro 2 nhánh (`C07` + `C09`), chống JOIN lỏng bằng `validate_findings`, `PRODUCTION_GATE`, C11 template engine với 22 ràng buộc `LIMITS` và slot binding | [group_c_compliance_and_risk.md](../modules/group_c_compliance_and_risk.md) · [`risks/aggregator.py`](../../backend/src/legal_checker/modules/risks/aggregator.py) · [`recommendations/generator.py`](../../backend/src/legal_checker/modules/recommendations/generator.py) |
| **08** | [08 — Report Generation & Human Review](08-report-generation-and-human-review.md) | Event log `C12` + lớp `effective` không ghi đè output AI, khóa lạc quan `expected_target_sha256`, `BLOCKING` publish gate, `ReportPresentation` single projection và Export SHA-256 | [group_d_report_and_frontend.md](../modules/group_d_report_and_frontend.md) · [`reviews/service.py`](../../backend/src/legal_checker/modules/reviews/service.py) · [`reports/presentation.py`](../../backend/src/legal_checker/modules/reports/presentation.py) |
| **09** | [09 — Async Workflow & Job Lifecycle](09-async-workflow-and-job-lifecycle.md) | Vòng đời Run `QUEUED → RUNNING → COMPLETED/FAILED`, `Idempotency-Key`, DB-first vs Redis, `Claim / Lease / Heartbeat`, `TransientRunError` retry và Celery Beat recovery | [demo.md](../guides/demo.md) · [`workflows/runner.py`](../../backend/src/legal_checker/workflows/runner.py) · [`worker/tasks/analysis_tasks.py`](../../backend/src/legal_checker/worker/tasks/analysis_tasks.py) |
| **10** | [10 — Unknown, Insufficient & Diagnostics](10-unknown-insufficient-and-diagnostics.md) | Phân biệt bản chất `UNKNOWN`, `INSUFFICIENT`, `MISSING`, `OUTSIDE_REVIEW_SCOPE`, `NOT_TRIGGERED`, `FAILED`; đọc `CoverageView`, `diagnostics` và cách tính mẫu số benchmark | [report_presentation.md](../contracts/report_presentation.md) · [`reports/assessment_status.py`](../../backend/src/legal_checker/modules/reports/assessment_status.py) · [`evaluator.py`](../../backend/src/legal_checker/modules/benchmarks/evaluator.py) |

---

## 3. Lộ trình đọc gợi ý cho Developer mới

1. **Hiểu toàn cảnh trong 30 phút:** Đọc tuần tự **01 → 02 → 09** để nắm bài toán, cách dữ liệu được pin và cách một request từ UI đi qua FastAPI/Celery/PostgreSQL.
2. **Đi sâu vào lõi pháp lý & AI (từ PDF tới kết luận):** Đọc **03 → 04 → 05 → 06**. Chú ý cách hệ thống tách rạch ròi:
   * *Điều khoản hợp đồng tự ghi (C03/C09)* vs *Luật thực sự áp dụng theo hồ sơ & thời điểm (C04/C05)*.
   * *Đề xuất ngữ nghĩa của LLM (`Observation`/`SemanticProposal`)* vs *Cổng kiểm chứng hậu kiểm (`Gates`, `Decimal`, `FullDocumentReviewer`)*.
3. **Đi sâu vào sản phẩm, rủi ro & vận hành:** Đọc **07 → 08 → 10** để hiểu vì sao UI không được phép làm logic nghiệp vụ, cách đọc bảng diagnostics khi gặp `UNKNOWN`, và cách C12 bảo vệ trách nhiệm pháp lý của người duyệt.
4. **Bắt tay code hoặc debug một module cụ thể:** Từ bảng mục lục ở trên, mở thẳng tài liệu `docs/modules/group_*.md` và file Python nguồn tương ứng.
