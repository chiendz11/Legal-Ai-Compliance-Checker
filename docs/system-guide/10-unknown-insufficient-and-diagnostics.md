# 10 — Unknown, Insufficient & Diagnostics

> **Tài liệu thẩm quyền liên quan:** [Report Presentation](../contracts/report_presentation.md) · [Gold Master R12](../guides/gold_master_20261114.md) · [Sửa verifier & coverage](../guides/hd360_followup_verification_20261108.md)  
> **Source code trung tâm:** [`reports/assessment_status.py`](../../backend/src/legal_checker/modules/reports/assessment_status.py) · [`reports/presentation.py`](../../backend/src/legal_checker/modules/reports/presentation.py) · [`compliance/requirement_aggregator.py`](../../backend/src/legal_checker/modules/compliance/requirement_aggregator.py) · [`benchmarks/evaluator.py`](../../backend/src/legal_checker/modules/benchmarks/evaluator.py)

---

## 1. Tư tưởng cốt lõi: Tại sao một hệ thống AI pháp lý trung thực lại có nhiều `UNKNOWN` và `INSUFFICIENT`?

Trong nhiều đồ án AI thông thường, người làm thường xem `UNKNOWN` là "lỗi chưa xử lý xong" và cố ép đầu ra về nhị phân (`Đạt` / `Không đạt`). Trong thẩm định pháp lý thực tế, hành động ép nhãn đó cực kỳ nguy hiểm:
* Một hợp đồng scan mờ 2 trang phụ lục không thể được kết luận là *"Đầy đủ điều khoản (SATISFIED)"* hay *"Thiếu điều khoản (MISSING)"*.
* Một bản dự thảo chưa ký, chưa có ngày giao kết giả định (`no date`) không thể tự bịa ra ngày hôm nay để chọn Luật Nhà ở 2023.
* Một hợp đồng đặt cọc không tồn tại trong dự thảo (`NOT_TRIGGERED`) không nên cộng vào tỷ lệ "đã tuân thủ".

Vì vậy, hệ thống phân biệt **6 khái niệm hoàn toàn khác nhau** mà developer và người dùng tuyệt đối không được đánh đồng:

| Khái niệm / Nhãn | Tầng sinh ra | Ý nghĩa chính xác | Được gộp vào lỗi / đạt không? |
|---|---|---|---|
| **`SATISFIED` / `VIOLATED`** (`Finding`) | C07 (chỉ khi `gates.reliable()`) | Có bằng chứng xác thực ủng hộ hoặc trái với predicate | Có (nhóm `ASSESSED`) |
| **`MISSING`** (`Finding`) | C07 (chỉ khi `gates.missing_allowed()`) | Nghĩa vụ bắt buộc + **đã chứng minh rà toàn văn** mà vắng mặt | Có (nhóm `ASSESSED`, kéo C08 thành `NON_COMPLIANT`/`PARTIAL`) |
| **`UNKNOWN`** (`Finding` / C09) | C04 / C05 / C07 / C09 | Đã nằm trong phạm vi đánh giá nhưng **chưa đủ dữ kiện / chưa verify / xung đột chứng cứ** | Có (`UNKNOWN` hợp pháp kèm `uncertainty_reason` — chuyển thành `VERIFICATION` risk) |
| **`INSUFFICIENT`** (`RequirementStatus`) | C08 (`AGG_CAN_HO_V1`) | Scope/version chưa chốt hoặc còn tiêu chí `UNKNOWN` (khi chưa có `VIOLATED`) | Không gộp thành `COMPLIANT` hay `NON_COMPLIANT` |
| **`OUTSIDE_REVIEW_SCOPE`** (Disposition) | `apply_review_scope()` | Nằm ngoài chế độ đã chọn (ví dụ mục thực hiện thực tế khi đang chạy `DRAFT_REVIEW`) | **Không phải `COMPLIANT`**, giữ tách riêng hoàn toàn khỏi `ASSESSED`! |
| **`NOT_TRIGGERED`** (Disposition) | `C07` (`conditional_review.py`) | Nghĩa vụ có điều kiện nhưng điều kiện phát sinh đã được chứng minh không xảy ra | **Không phải `SATISFIED`**, giữ tách riêng hoàn toàn khỏi `ASSESSED`! |
| **`FAILED`** (`RunStatus`) | `runner.py` | Lỗi kỹ thuật/hạ tầng/contract khiến tiến trình dừng ngang | Tuyệt đối không phải nhãn pháp lý |

---

## 2. Truy dấu mọi nguồn gốc sinh ra `UNKNOWN` & `INSUFFICIENT` qua C02 → C11

Khi mở một báo cáo thấy nhiều dòng `INSUFFICIENT` hoặc `UNKNOWN`, hãy lần theo đúng 6 cổng sau để biết nguyên nhân nằm ở tầng nào:

### Tầng 1 — Document Intelligence (`C02`)
* Trang PDF scan là ảnh không có text layer (`all_pages_have_text == False` trong `DocumentReadCoverage`) → mọi suy luận đòi phủ toàn văn (như `MISSING`, `PROHIBITED_CLAUSE` vắng mặt) tự động chặn ở `absence_verified = False`.
* Facts do LLM đề xuất mang `trang_thai = "DERIVED_REVIEW_PENDING"`, chưa được nguồn rule/reviewer xác thực → các kiểm tra số học (`numeric_rules.py`) đòi `facts_verified == True` sẽ dừng ở `UNKNOWN`.

### Tầng 2 — Scope & Temporal (`C04` / `C05`)
* Thiếu thông tin phân loại (ví dụ chưa rõ dự án có thuộc nhà ở xã hội hay không) → `scope_status = "UNKNOWN"` theo Kleene logic.
* Thiếu ngày giao kết (`SIGNING`) và C01 không khai báo mốc giả định → **hàng trăm family giữ `version_status = "UNKNOWN"`**, kéo theo `C08` giữ `INSUFFICIENT` (kèm disposition `LEGAL_SCOPE_UNRESOLVED`).
* Hợp đồng ký từ `01/08/2024` nhưng thiếu fact chuyển tiếp `transition.future_sale_eligible_before_20240801` → giữ `UNKNOWN` theo Điều 83(5) Luật KDBĐS 2023.
* Yêu cầu dùng `TEMPLATE_USE` hoặc `PRE_HANDOVER_COLLECTION` mà hợp đồng chỉ có ngày `SIGNING` → không dùng ngày ký thay thế.

### Tầng 3 — Retrieval & Selective Full-Document Review (`C06` → `C07`)
* `ASSESSMENT_MODULES=modules` chạy chế độ mặc định **offline** (không bật `LLMObservationProvider` / `FullDocumentReviewer`): Retrieval chỉ lấy được đoạn trích ứng viên (`C06`), chưa có adapter ngữ nghĩa & xác minh quote nên C07 trung thực trả `UNKNOWN` (`LLM / verifier not configured`).
* `FullDocumentReviewer` có một batch lỗi hoặc trả `UNCERTAIN` → không thể chứng minh điều khoản vắng mặt trên toàn văn (`absence_verified = False`).

### Tầng 4 — Compliance Gates & Conflicts (`C07`)
* Phát hiện mâu thuẫn giữa thân hợp đồng và phụ lục (hai mức giá bán khác nhau, hai ngày bàn giao khác nhau, hai tài khoản khác nhau) → `gates.evidence_conflict = True` → giữ `UNKNOWN` để chuyển người dùng xác minh, không tự chọn bừa một con số.
* Có điều khoản ngoại lệ trong `ngoai_le_ap_dung` nhưng chưa có dữ kiện loại trừ → `gates.exceptions_resolved = False`.

### Tầng 5 — Citation Validation (`C09`)
* Hợp đồng chỉ dẫn chung chung *"theo Luật Nhà ở hiện hành"* hoặc ghi tên + năm không rõ số hiệu → `NAME_ONLY_VERSION_IDENTITY_AMBIGUOUS` → `status = "UNKNOWN"`.
* Số hiệu văn bản (ví dụ quyết định riêng của tỉnh) không có trong catalog `van_ban_phap_ly` pin sẵn → `UNKNOWN`, không ép thành `INVALID`.

---

## 3. Đọc hiểu `CoverageView`, `diagnostics` và Mẫu số Đánh giá (`GoldBenchmarkEvaluator`)

### 3.1. `CoverageView` (`reports/presentation.py`): tách "đủ dòng kết quả" khỏi "đủ bằng chứng toàn văn"
Một lỗi hiểu nhầm rất phổ biến là nhìn thấy `coverage_complete = False` rồi tưởng pipeline bị mất tiêu chí. Hàm `coverage_view()` phân tách rõ 3 cờ độc lập:
1. **`finding_complete` (`Đã có đủ kết quả tiêu chí`):** Mọi criterion thuộc phiên bản requirement đã chạy có đủ 1 dòng `CriterionResult` chưa?
2. **`full_text_complete` (`Đã xác nhận độ phủ bằng chứng toàn văn`):** Đã quét toàn bộ các trang/phụ lục để chứng minh sự vắng mặt hay chưa? (Chưa xác nhận toàn văn **không đồng nghĩa** thiếu dòng kết quả tiêu chí!).
3. **`conclusion_complete` (`row.coverage_complete` ở `C08`):** Dựa trên toàn bộ tiêu chí bắt buộc, kết luận tổng hợp ở mức family đã khép kín chưa hay còn tiêu chí `UNKNOWN` treo bên dưới (ví dụ có 1 tiêu chí đã `VIOLATED` làm family thành `NON_COMPLIANT`, nhưng 1 tiêu chí khác vẫn đang `UNKNOWN` → `conclusion_complete = False`).

### 3.2. Bảng `diagnostics` trên `AssessmentDraft` và `FinalReport`
Mỗi module khi gặp thiếu dữ kiện hệ thống đều có thể gắn diagnostic có cấu trúc (`module`, `code`, `subject_id`, `detail`), ví dụ:
* `RETRIEVAL_NOT_RUN` (C06 bị tắt hoặc bỏ qua)
* `C09_INPUT_EMPTY` (chưa chạy nhánh kiểm định viện dẫn)
* `UNSUPPORTED_CITATION_GUARD` (C10 gặp trigger guard chưa hỗ trợ)
* Mã lỗi ở tầng `C11` khi thiếu slot biến bắt buộc trong template.

Các bảng diagnostic này giúp kỹ sư phân biệt ngay giữa **thiếu dữ liệu đầu vào hợp đồng** với **thiếu cấu hình/module lúc chạy**.

### 3.3. Tính mẫu số chuẩn trong [`GoldBenchmarkEvaluator`](../../backend/src/legal_checker/modules/benchmarks/evaluator.py)

Khi chấm benchmark trên bộ **Gold Master**, nguyên tắc thống kê bắt buộc ở mọi tầng là **dùng đúng mẫu số, tuyệt đối không làm méo điểm**:
* **C07 (`Criterion Evaluation`):** Chỉ tính Precision / Recall / Macro-F1 trên các dòng thuộc nhóm **`ASSESSED`** (ví dụ trong R12 là `18.149` dòng: `12.562 SATISFIED`, `1.239 VIOLATED`, `424 MISSING`, `3.924 UNKNOWN có lý do nguồn`). Các dòng **`OUTSIDE_REVIEW_SCOPE` (`9.997`), `NOT_TRIGGERED` (`971`) và `SCOPE_UNRESOLVED` (`4.904`)** được kiểm tra đúng disposition nhưng **tách riêng**, không bao giờ trộn vào mẫu số của `UNKNOWN` pháp lý!
* **C06 (`Retrieval`):** Đo `Recall@K` / `MRR` trên **`RETRIEVAL_JUDGED_POOL`** (`73.519` dòng đã chấm). Mọi chunk ngoài pool mang nhãn `UNJUDGED`, không mặc định coi là sai.
* **Tổng thể `140` ca `PENDING_ADJUDICATION`:** Không đưa vào tử số hay mẫu số của bất kỳ bảng điểm nào cho tới khi hoàn tất biên soạn đủ `360/360` ca (`full_e2e_gold_ready == true`).

---

## 4. Tổng kết bộ System Deep Dive

Đến đây, bạn đã đi xuyên suốt toàn bộ kiến trúc logic của `Legal-Ai-Compliance-Checker`:
* **Từ PDF nguyên bản → Chunk giữ nguyên văn → C02/C03 có quote & SHA-256** ([Bài 03](03-document-intelligence.md))
* **Tách Nhánh A (C04 Kleene Scope + C05 Half-Open Interval & Chuyển tiếp) khỏi Nhánh B (C09 Citation)** ([Bài 04](04-scope-and-temporal-resolution.md), [Bài 05](05-citation-validation-and-retrieval.md))
* **Tìm kiếm C06 + Rà toàn văn → Chấm thuần C07 qua 8 Gates & Decimal → Tổng hợp C08 `AGG_CAN_HO_V1`** ([Bài 05](05-citation-validation-and-retrieval.md), [Bài 06](06-compliance-reasoning-and-c07-c08.md))
* **Hợp nhất C10 có provenance + Render C11 theo 22 `LIMITS` → C12 Event Overlay & C13 Export có dấu SHA-256** ([Bài 07](07-risk-and-recommendation.md), [Bài 08](08-report-generation-and-human-review.md))
* **Vận hành tin cậy qua Queue/Lease/Heartbeat & Trung thực với mọi trạng thái `UNKNOWN`/`INSUFFICIENT`** ([Bài 09](09-async-workflow-and-job-lifecycle.md), [Bài 10](10-unknown-insufficient-and-diagnostics.md)).

Quay về mục lục tổng hợp: [docs/system-guide/README.md](README.md) · [docs/README.md](../README.md).
