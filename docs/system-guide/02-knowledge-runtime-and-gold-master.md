# 02 — Knowledge, Runtime & Gold Master

> **Tài liệu thẩm quyền liên quan:** [Cơ sở dữ liệu & Seed](../database/local_setup.md) · [Dataset PDF360 v4 r2](../guides/dataset_pdf360_v4r2_runtime_20261110.md) · [Gold Master thống nhất R12](../guides/gold_master_20261114.md) · [Database Catalog](../contracts/database_catalog.json)  
> **Source code trung tâm:** [`legal_knowledge/models.py`](../../backend/src/legal_checker/modules/legal_knowledge/models.py) · [`legal_knowledge/postgres_repository.py`](../../backend/src/legal_checker/modules/legal_knowledge/postgres_repository.py) · [`assessments/integrity.py`](../../backend/src/legal_checker/modules/assessments/integrity.py) · [`benchmarks/evaluator.py`](../../backend/src/legal_checker/modules/benchmarks/evaluator.py)

---

## 0. Trình bày nhanh (đọc phần này trước khi thuyết trình)

> **Một câu:** Luật, dữ liệu chạy thật và đáp án kiểm thử được cất ở ba nơi tách biệt; mỗi lượt chạy ghi rõ nó dùng “bản chụp” tri thức nào, nên báo cáo cũ không đổi khi luật được cập nhật và đáp án không thể rò vào hệ thống.

**Hình dung đời thường.** Kho tri thức giống một bộ luật in thành sách có số ấn bản. Mỗi báo cáo ghi rõ “soạn theo ấn bản số mấy” (mã băm SHA-256). Khi có ấn bản mới, báo cáo cũ vẫn trích đúng ấn bản cũ. Còn Gold Master giống bộ đề thi có đáp án: người chấm cầm đáp án, thí sinh (pipeline) không bao giờ được nhìn.

**Ba ý phải nói được:**

1. **Ba miền dữ liệu:** Knowledge (tri thức, bất biến theo snapshot) · Runtime (ca, lượt chạy, báo cáo, review) · QA/Gold (đáp án, chia DEV/VAL/TEST).
2. **Ghim (pin) bằng SHA-256:** `knowledge_snapshot_sha256` đi cùng mọi lượt chạy; lệch mã băm là dừng.
3. **Kỷ luật công bố:** Gold Master R12 mới có 220/360 ca và chưa có luật sư độc lập ký duyệt, nên chưa công bố accuracy/F1 tổng thể.

**Thuật ngữ dùng trong chương:**

| Thuật ngữ | Nghĩa dễ hiểu |
|---|---|
| KnowledgeSnapshot | Bản đóng băng toàn bộ tri thức pháp lý tại một thời điểm, có mã băm. |
| Pin / ghim | Ghi cố định phiên bản đang dùng để chạy lại ra đúng kết quả cũ. |
| `draft_json` | Kết quả đầy đủ của một lượt chạy — nguồn sống duy nhất mà UI/API đọc. |
| Gold Master | Bộ đáp án chuẩn nhiều lớp (facts → C05 → C06 → C07 → …) dùng để chấm. |
| `REFERENCE_REPLAY` | Chế độ phát lại dữ liệu mẫu để thử UI; không phải kết quả suy luận thật. |

**Slide tương ứng:** 11–13 và 41 trong [deck Công nghệ C01–C13](../business/slides/cong_nghe_va_ky_thuat_he_thong_c01_c13.pptx) · **Thời lượng gợi ý:** 4–5 phút.

---

## 1. Tại sao phải tách 3 miền dữ liệu: Knowledge, Runtime và QA/Gold?

Trong các dự án AI pháp lý thông thường, đội ngũ rất dễ gộp chung tri thức luật, dữ liệu chạy thật của người dùng và đáp án kiểm thử vào một schema duy nhất. Cách làm đó gây ra 3 thảm họa kỹ thuật:

1. **Sửa một dòng luật làm méo kết quả báo cáo cũ:** Nếu kết quả chạy hợp đồng chỉ lưu `requirement_id = "FAM_BAO_HANH"` rồi `JOIN` trực tiếp với bảng luật đang sửa, báo cáo năm ngoái tự nhiên đổi nội dung khi bạn cập nhật luật năm nay.
2. **Rò rỉ đáp án mẫu vào luồng suy luận thật (Data Leakage):** Nếu bảng runtime dùng chung bảng với đáp án Gold/reference, code hoặc câu truy vấn vô tình đọc nhầm nhãn mẫu sẽ tạo ra ảo giác hệ thống đạt độ chính xác 100%.
3. **Không thể tái lập (Non-reproducible runs):** Không biết kết luận tuần trước được sinh ra trên phiên bản luật nào, chunker nào hay prompt nào.

Do đó, hệ thống tách cứng 3 miền dữ liệu hoàn toàn độc lập:

```
┌──────────────────────────────────┐   pin bằng SHA-256    ┌───────────────────────────────────┐
│        1. KNOWLEDGE DOMAIN       │ ────────────────────► │         2. RUNTIME DOMAIN         │
│ • 18 bảng tri thức pháp luật     │                       │ • Case, source PDF, chunks, C02/03│
│ • Luật, điều khoản, phạm vi,     │                       │ • workflow_runs.draft_json        │
│   phiên bản, tiêu chí, mẫu rủi ro│                       │ • report_versions + C12 reviews   │
│ • Export thành KnowledgeSnapshot │                       │ • assessment_runs (Nhóm C)        │
└──────────────────────────────────┘                       └───────────────────────────────────┘
                                                                          │
                                                                 đánh giá độc lập
                                                                          ▼
                                                           ┌───────────────────────────────────┐
                                                           │         3. QA / GOLD DOMAIN       │
                                                           │ • Gold Master SQLite/JSONL/XLSX   │
                                                           │ • Phân tách DEV / VAL / TEST      │
                                                           │ • GoldBenchmarkEvaluator          │
                                                           └───────────────────────────────────┘
```

---

## 2. Knowledge Domain: Snapshot bất biến và cơ chế Pinning (`X01`)

### Tổ chức của Kho Tri thức (18 bảng)

Kho tri thức pháp lý chứa cấu trúc phân cấp chặt chẽ từ văn bản luật đến mẫu khuyến nghị:
* **Tầng văn bản nguồn:** `van_ban_phap_ly`, `dieu_khoan_phap_ly`, `quan_he_van_ban` (sửa đổi, bổ sung, thay thế, hết hiệu lực).
* **Tầng yêu cầu & phạm vi:** `loai_hop_dong` (cây phân cấp loại hợp đồng qua `loai_cha_id`), `yeu_cau_phap_ly` (**323 requirement families** trong snapshot hiện hành), `pham_vi_ap_dung` (điều kiện JSON predicate + `nhom_phien_ban`), `phien_ban_yeu_cau` (hiệu lực `[hieu_luc_tu, hieu_luc_den)`, `loai_moc_ap_dung`, `quy_tac_chuyen_tiep`), `nguon_yeu_cau`.
* **Tầng đánh giá & hành động:** `tieu_chi_danh_gia` (**479 criteria** trong snapshot hiện hành), `quy_tac_quyet_dinh`, `quy_tac_tong_hop` (`AGG_CAN_HO_V1`), `ngoai_le_ap_dung`, `quy_tac_rui_ro`, `mau_khuyen_nghi`.

### Tại sao mọi Run phải đọc từ `KnowledgeSnapshot` đã Pin thay vì query tự do?

* Khi quản trị viên xuất bản tri thức qua `KnowledgeCurationService.publish_snapshot()`, hệ thống đóng băng toàn bộ dữ liệu tri thức và tính **SHA-256 (`knowledge_snapshot_sha256`)**. Hiện tại snapshot baseline chuẩn của dự án có hash `4ab2d7ea296ea908e25c09fcb6d5f073f1ebe1917678b36390f803b1c725804a`.
* Khi khởi tạo một `Context` cho run (`shared/contracts/common.py`), 4 trục pin bắt buộc đi cùng nhau trong `DeploymentPin` / `X01`:
  * `phien_ban_id` (phiên bản cấu hình deployment)
  * `rule_version` (phiên bản bộ rule C07/C08/C10/C11)
  * `legal_knowledge_version`
  * `knowledge_snapshot_sha256` (64 hex chars, bắt buộc khớp với `knowledge.sha256` ở mọi hàm `validate_context()`, `validate_requirements()`, `validate_findings()`).
* **Lợi ích:** Dù bên ngoài database đang biên soạn thêm nghị định mới (draft/unverified), worker đang chạy giữa chừng vẫn nhìn thấy cùng một thế giới tri thức bất biến từ Stage 1 đến Stage 9. Mọi `CriterionResult` (C07) thậm chí nhúng bản sao `tieu_chi_snapshot_json` và `knowledge_snapshot_sha256` để kiểm tra chéo ở bước C10/C13.

> **Các trục version độc lập:** Không bao giờ dùng một con số (như `v7.4.9` — vốn là tên baseline migration SQL) để đại diện cho tất cả. Hệ thống tách riêng: `PDF SHA-256` · `extraction_version` (chunker/parser) · `dataset release` (`PDF360 v4 r2`) · `knowledge_snapshot_sha256` · `rule/model/prompt version` · `Alembic revision`.

---

## 3. Runtime Domain: Lưu gì và đâu là "Source of Truth"?

Một điểm hay gây nhầm lẫn cho dev mới là phân biệt giữa **dữ liệu nguồn sống (live runtime)** với **bảng phụ trợ / bản phát triển riêng của nhóm C**.

| Thành phần | Vị trí lưu trữ thật | Mục đích & Lưu ý quan trọng |
|---|---|---|
| **Hồ sơ hợp đồng & source** | Bảng `contracts`, `assessment_cases`, storage local/HTTP theo SHA | Giữ bytes PDF thật và metadata đầu vào C01; `SourceStorage.read()` đối chiếu lại SHA-256 trước khi parse. |
| **Extraction đã chuẩn hóa** | `doan_hop_dong`, `ho_so_trich_xuat`, `vien_dan_hop_dong` | Retrieval hiện đọc metadata đường dẫn mục (`section_paths`) và fact evidence từ DB theo đúng `extraction_version` đang active. |
| **Output toàn pipeline (Live)** | `runtime.workflow_runs.draft_json` | Đây là **nguồn sống duy nhất** của kết quả chạy full-pipeline qua API/UI (`AssessmentDraft`). |
| **Báo cáo phiên bản** | `runtime.report_versions` + `report_exports` | Mỗi lần tạo báo cáo hoặc review mới tạo một `report_version` bất biến mới, kèm SHA-256. |
| **Sự kiện duyệt con người** | Bảng reviews (`C12`) | Append-only event log trỏ vào `run_id` và `expected_target_sha256`, không bao giờ sửa ngược `draft_json`. |
| **Standalone Nhóm C** | `assessment_runs` | Bảng persistence phục vụ nhóm C phát triển/test C07–C11 độc lập (`run_group_c.py`), **không thay thế** `workflow_runs` ở chế độ integrated full-pipeline. |

---

## 4. QA & Gold Master Domain: Tại sao phải có bộ Gold nhiều lớp?

### Phân biệt 3 khái niệm rất dễ nhầm: `SILVER` vs `Scoped Gold` vs `E2E Gold Master`

* **Pipeline Output / `SILVER` / `Proposals`:** Là kết quả do máy tự chạy ra. Tuyệt đối **không bao giờ** dùng làm đáp án chuẩn (Ground Truth) để chấm chính hệ thống.
* **`Scoped Gold`:** Các bộ đáp án chấm riêng từng phần hẹp hoặc từng lát cắt (ví dụ: 36 trường literal ở phần phụ lục `APPENDIX_LITERALS`, hoặc danh sách số hiệu nhận diện được ở `NUMBERED_MENTIONS`), dùng để kiểm tra độ hồi tưởng/độ chính xác cục bộ của một module nhỏ, **không đủ chứng minh độ chính xác E2E của toàn hợp đồng**.
* **`Gold Master` thống nhất (hiện tại `R12` — 16/11/2026):** Là một nguồn đáp án thống nhất bằng SQLite / JSONL / Excel dùng **cùng bộ PDF (`PDF360 v4 r2`), cùng `KnowledgeSnapshot` và cùng policy đã khóa**. Mỗi ca trong Gold Master gồm nhiều lớp đáp án liên thông từ `APPENDIX_LITERALS → FACTS → SCOPE_TEMPORAL (C05) → RETRIEVAL_JUDGED_POOL (C06) → CRITERIA (C07) → AGGREGATION (C08) → CITATION_OCCURRENCES (C09) → RISKS (C10) → RECOMMENDATION_ASSERTIONS (C11) → REVIEW_POLICY / REPORT_ASSERTIONS (C12/C13)`.

### Hiện trạng & Kỷ luật công bố của Gold Master R12

Theo [Gold Master R12](../guides/gold_master_20261114.md) và [`GoldBenchmarkEvaluator`](../../backend/src/legal_checker/modules/benchmarks/evaluator.py):

1. **Tổng số ca đã đăng ký:** `360` ca (`90` nhóm nguồn × `4` biến thể: baseline, missing, adverse, conflict/no-date) thuộc bộ `PDF360 v4 r2`, chia tách chặt chẽ **DEV / VALIDATION / TEST** (`240 DEV / 60 VAL / 60 TEST`).
2. **Tiến độ R12 (16/11/2026):** Đã biên soạn **220/360 ca (61,1%)** thuộc `55/90` nhóm nguồn (`100 DEV + 60 VALIDATION + 60 TEST` trong Master; riêng gói TEAM dành cho dev chỉ phát `160/300` ca DEV/VAL). Còn **140 ca DEV (`35` nhóm nguồn)** ở trạng thái `PENDING_ADJUDICATION`.
3. **Bảo vệ tập TEST chống rò rỉ:** Gói `TEST INPUTS` phát cho người chạy chỉ chứa 60 PDF + metadata C01 + snapshot chung; đáp án TEST nằm riêng trong gói Master dành cho `GoldBenchmarkEvaluator`.
4. **Cổng phát hành (`FULL_RELEASE_GATE.json`) & Provenance bắt buộc:**
   * `adjudicator_type = "AI_SOURCE_ADJUDICATED"` và `human_legal_signoff = false`: ghi nhận minh bạch đây là đáp án do quá trình đọc trực tiếp PDF + đối chiếu luật xây dựng, chưa phải thẩm định ký duyệt của luật sư độc lập.
   * `production_outputs_used = false`: không lấy output pipeline hay `REFERENCE_REPLAY` chép vào Gold.
   * `full_e2e_gold_ready = false`: Chỉ khi đủ **360/360 ca** hoàn tất kiểm tra toàn vẹn mọi lớp, cờ này mới chuyển `true`. Vì thế ở thời điểm hiện tại, dự án giữ kỷ luật **không công bố chỉ số accuracy/F1 tổng thể toàn pipeline**.

---

## 5. Chú ý khi chạy chế độ `MODULES` vs `REFERENCE_REPLAY`

Hệ thống hỗ trợ biến môi trường `ASSESSMENT_MODULES` (`api/dependencies.py`, `workflows/runner.py`):
* **`modules` (IntegratedModulesSource):** Chạy toàn bộ code thật `PdfDocumentIntelligence → Scope → Temporal → Citation → Retrieval → Compliance → Risk → Recommendation` trên bytes PDF thật. Đây là chế độ duy nhất hợp lệ cho đánh giá hệ thống.
* **`reference` (`ReferenceReplaySource`):** Chỉ phát lại (replay) payload reference đã seed sẵn trong DB cho mục đích **test UI, queue và luồng C12/C13** mà không chạy inference thật. Tuyệt đối không dùng kết quả `REFERENCE_REPLAY` để báo cáo độ chính xác của AI/rule engine.

---

## Hỏi – đáp khi trình bày

**Hỏi: Kho tri thức lớn cỡ nào?**  
Đáp: Đếm trực tiếp trong schema `knowledge` ngày 17/11/2026: 37 văn bản, 2.074 điều khoản, 323 nhóm yêu cầu, 357 phiên bản yêu cầu, 479 tiêu chí, 1.916 quy tắc quyết định, 1.161 mẫu rủi ro và 1.161 mẫu khuyến nghị. Đây là quy mô biên soạn, không phải bằng chứng độ chính xác.

**Hỏi: Sửa một điều luật thì báo cáo cũ có đổi không?**  
Đáp: Không. Sửa xong phải xuất snapshot mới (mã băm mới). Báo cáo cũ vẫn gắn mã băm cũ và còn nhúng bản sao tiêu chí tại thời điểm chạy.

**Hỏi: Độ chính xác của hệ thống là bao nhiêu?**  
Đáp: Chưa công bố chỉ số tổng. `full_e2e_gold_ready=false` vì mới biên soạn 220/360 ca; đáp án hiện là `AI_SOURCE_ADJUDICATED`, `human_legal_signoff=false`.

**Hiểu lầm hay gặp cần tránh khi nói:**

* `v7.4.9` là tên baseline migration SQL, không phải “phiên bản hệ thống”. Mỗi trục (PDF, chunker, snapshot, rule, prompt) có phiên bản riêng.
* Kết quả pipeline (SILVER) không bao giờ là đáp án để chấm chính pipeline.

---

## 6. Đọc tiếp & Tham chiếu nhanh

* **Bước kế tiếp trong bộ Deep Dive:** [03 — Document Intelligence](03-document-intelligence.md)
* **Đối chiếu code:**
  * [`KnowledgeSnapshot`](../../backend/src/legal_checker/modules/legal_knowledge/models.py) — mô hình snapshot bất biến và `legal_basis()`.
  * [`validate_pinned_knowledge`](../../backend/src/legal_checker/modules/assessments/integrity.py) — kiểm tra tính toàn vẹn SHA-256 giữa case, context và snapshot.
  * [`GoldBenchmarkEvaluator`](../../backend/src/legal_checker/modules/benchmarks/evaluator.py) — đọc `GOLD_COVERAGE.json`, `FULL_RELEASE_GATE.json` và chấm C05/C06/C07.
