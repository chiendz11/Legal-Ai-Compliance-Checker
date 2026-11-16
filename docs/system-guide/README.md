# System Deep Dive — Hướng dẫn Chuyên sâu Hệ thống Legal AI Compliance Checker

> **Vai trò của bộ tài liệu này:** Giải thích *tại sao* hệ thống được thiết kế như hiện nay, *cách thuật toán vận hành*, *dữ liệu biến đổi qua từng contract C01–C13*, các *trade-off kỹ thuật*, và *ánh xạ trực tiếp tới class/function trong source code* bằng các tình huống thực tế của hợp đồng mua bán căn hộ tại Việt Nam.

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
| **03** | [03 — Document Intelligence](03-document-intelligence.md) | Intake kiểm SHA-256, `PdfTextReader`, thuật toán chunking giữ offset nguyên văn (`structural-sentences-v2`), rule extractor vs `SemanticDocumentExtractor` (`Qwen`/Ollama) và C03 | [group_a_document_intelligence.md](../modules/group_a_document_intelligence.md) · [documents_local_llm.md](../modules/documents_local_llm.md) · [`modules/documents/`](../../backend/src/legal_checker/modules/documents/service.py) |
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
