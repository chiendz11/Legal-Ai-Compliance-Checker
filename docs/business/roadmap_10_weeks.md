# Kế hoạch Triển khai 10 Tuần — Legal Compliance Checker

> **Giai đoạn**: Tuần 4 – Tuần 13  
> **Quy mô**: 5 Thành viên · 5 Workstreams · 4 Modules AI/Rule · 1 Central Database

---

## 1. Phân công Vai trò & Ownership

| Thành viên | Vai trò | Ownership chính | Input chính | Output chính | Service / Component |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Người 1** | Data & DevOps Engineer | Gold Legal DB, sample runtime/gold labels, schema/migrations/seed, shared Compose, CI/CD, GitOps & hạ tầng k3d | Nguồn luật + hợp đồng mẫu + yêu cầu hạ tầng | Knowledge + Runtime seed + data contracts + shared development environment | `data-release`, `shared-devops` |
| **Người 2** | Document Intelligence Engineer | PDF/DOCX OCR/parser, chunking, metadata/classification, citation extraction, document API | Hợp đồng PDF/DOCX + Runtime mẫu | `contract_profile` + chunks + extracted citations (C01, C02, C03) | `document-service` (module `documents`) |
| **Người 3** | Legal Scope, Citation & Retrieval Engineer | Scope/Checklist, temporal/version resolver, citation validator; requirement→chunk retrieval, evaluation, serving | profile + citations + Gold DB + chunks | Applicable requirement versions (C04, C05) + citation findings (C09) + Top-K evidence (C06) | `legal-engine`, `retrieval-service` (modules `applicable_law`, `citation_validation`, `retrieval`) |
| **Người 4** | Compliance Reasoning & Risk Engineer | Criterion/compliance reasoning, grounded explanation, substantive risk, recommendation và service API | Requirement version + evidence (C05, C06) | Compliance label + explanation (C07, C08) + substantive risk (C10) + recommendation (C11) | `reasoning-service` (modules `compliance`, `risks`, `recommendations`) |
| **Người 5** | Integration, UI & Platform Engineer | Orchestrator, async workflow, frontend, report, application deployment/monitoring, E2E tests | Outputs các services + shared DevOps nền | End-to-end dashboard/report + application release (C12, C13) | `backend/orchestrator`, `frontend` (modules `assessments`, `reports`, `workflows`) |

---

## 2. Luồng End-to-End

```text
[1. Upload Hợp đồng] (Người 5)
        │
        ▼ (file_uri)
[2. Document Intelligence] (Người 2) ──► OCR, chunking, facts, citations (C01, C02, C03)
        │
        ├─────────────────────────────────────────┐
        ▼ (profile)                               ▼ (citations)
[3A. Scope & Temporal Resolver] (Người 3)   [3B. Citation Validator] (Người 3)
        │ ──► Applicable Requirements (C04, C05)   │ ──► Citation Findings (C09)
        ▼                                          │
[4. Hybrid Retrieval] (Người 3)                    │
        │ ──► Top-K Evidence Chunks (C06)          │
        ▼                                          │
[5. Compliance Reasoning] (Người 4)                │
        │ ──► Criterion Outcomes & Labels (C07, C08)│
        ▼                                          │
[6. Risk & Recommendation] (Người 4) ◄─────────────┘ (hợp nhất 2 nhánh)
        │ ──► Substantive Risks (C10) & Recommendations (C11)
        ▼
[7. Aggregation, Report & UI] (Người 5) ──► Review events (C12), Final Report (C13), UI Dashboard
```

---

## 3. Lộ trình 3 Giai đoạn (Tuần 4 – Tuần 13)

### Giai đoạn 1: Nghiên cứu, BRD & Thiết kế Kiến trúc (Tuần 4 – Tuần 6)
- **Tuần 4**: Khảo sát bài toán khi chưa có dataset; phân tích nghiệp vụ HĐMB căn hộ và hai nhánh kiểm tra pháp lý.
- **Tuần 5**: Soạn thảo **BRD v1.1**; chốt ranh giới trách nhiệm 5 workstreams, use cases và tiêu chí nghiệm thu.
- **Tuần 6**: Thiết kế kiến trúc tổng thể, hệ thống Data Contracts (C01–C13, X01–X02), PostgreSQL schema và kế hoạch tạo dữ liệu.

### Giai đoạn 2: Tạo Dữ liệu, Xây dựng Modules & Inference (Tuần 7 – Tuần 11)
- **Tuần 7** *(Đã hoàn thành)*:
  - Người 1: Hoàn thành Knowledge Data (36 văn bản luật, 306 yêu cầu) và Development Fixtures (240 DEV / 60 VAL).
  - Người 5: Hoàn thành cấu trúc Frontend cơ bản.
  - Người 2–4: Đặc tả fixture inputs/expected outputs cho từng module.
- **Tuần 8** *(Đã hoàn thành phần lớn)*:
  - Người 1: CI/CD test baseline, GHCR Docker publish, GitOps Argo CD tự động và Terraform local k3d.
  - Người 3: Hoàn thành và merge Nhóm B (Bước 3A, 3B, 4) vào `main` (PR #10).
  - Người 4: Hoàn thành và merge Nhóm C (Bước 5, 6, 7) vào `main` (PR #11).
  - Người 2: Đang hoàn thiện Document Intelligence API (parser/OCR).
  - Người 5: Chuẩn bị Integration Baseline.
- **Tuần 9** *(Mục tiêu trọng tâm)*:
  - Hoàn thiện module `documents` (Người 2) để kết nối file PDF thật vào pipeline.
  - Integration baseline $\rightarrow$ **First Working Inference**: Chạy thử nghiệm thành công 1 hợp đồng PDF thật từ đầu vào đến báo cáo cuối cùng.
- **Tuần 10**:
  - Mở rộng độ phủ trên nhiều file PDF DEV đại diện; hoàn thiện Inference MVP.
- **Tuần 11**:
  - Ổn định hệ thống, xử lý trường hợp bất định (`UNKNOWN`), benchmark hiệu năng và kiểm thử hồi quy (regression tests).

### Giai đoạn 3: Tính năng Sản phẩm, QA & Bàn giao (Tuần 12 – Tuần 13)
- **Tuần 12**:
  - Hoàn thiện các tính năng mở rộng: Lịch sử upload, tìm kiếm/lọc hợp đồng, xem chi tiết nguồn trích dẫn, xuất báo cáo PDF/JSON.
- **Tuần 13**:
  - Đánh giá tổng thể độ chính xác trên tập kiểm chứng độc lập.
  - Diễn tập demo, hoàn thiện tài liệu bàn giao và báo cáo tổng kết đồ án.
