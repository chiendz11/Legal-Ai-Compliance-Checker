# 10 — Unknown, Insufficient & Diagnostics

> **Tài liệu thẩm quyền liên quan:** [Report Presentation](../contracts/report_presentation.md) · [Gold Master R12](../guides/gold_master_20261114.md) · [Sửa verifier & coverage](../guides/hd360_followup_verification_20261108.md)  
> **Source code trung tâm:** [`reports/assessment_status.py`](../../backend/src/legal_checker/modules/reports/assessment_status.py) · [`reports/presentation.py`](../../backend/src/legal_checker/modules/reports/presentation.py) · [`compliance/requirement_aggregator.py`](../../backend/src/legal_checker/modules/compliance/requirement_aggregator.py) · [`benchmarks/evaluator.py`](../../backend/src/legal_checker/modules/benchmarks/evaluator.py)

---

## 0. Trình bày nhanh (đọc phần này trước khi thuyết trình)

> **Một câu:** `UNKNOWN` và `INSUFFICIENT` không phải lỗi chưa làm xong: đó là cách hệ thống từ chối đoán khi thiếu căn cứ, và mỗi trường hợp đều kèm lý do để biết cần bổ sung gì.

**Hình dung đời thường.** Một bác sĩ cẩn thận không kết luận “khoẻ mạnh” khi thiếu kết quả xét nghiệm, cũng không kết luận “có bệnh”. Bác sĩ ghi “chưa đủ căn cứ, cần làm thêm xét nghiệm X”. `UNKNOWN` chính là dòng ghi chú đó. Ngoài ra còn hai dòng khác hẳn: “không thuộc đợt khám này” (`OUTSIDE_REVIEW_SCOPE`) và “không có triệu chứng nên không cần xét” (`NOT_TRIGGERED`).

**Ba ý phải nói được:**

1. **Phân biệt các nhãn:** `SATISFIED`/`VIOLATED`/`MISSING` (đã chấm) · `UNKNOWN` (trong phạm vi, thiếu căn cứ) · `INSUFFICIENT` (mức yêu cầu) · `OUTSIDE_REVIEW_SCOPE` · `NOT_TRIGGERED` · `FAILED` (kỹ thuật).
2. **Lần theo tầng sinh ra `UNKNOWN`:** đọc tài liệu → phạm vi/thời gian → truy xuất/rà toàn văn → cổng kiểm chứng → viện dẫn → *giới hạn cấu hình khi chạy*.
3. **Đúng mẫu số khi chấm:** chỉ tính P/R/F1 trên nhóm `ASSESSED`; các nhóm khác kiểm riêng.

**Thuật ngữ dùng trong chương:**

| Thuật ngữ | Nghĩa dễ hiểu |
|---|---|
| `uncertainty_reason` | Lý do cụ thể khiến một tiêu chí ở `UNKNOWN`. |
| Disposition | Cách xử lý vận hành: `ASSESSED`, `OUTSIDE_REVIEW_SCOPE`, `NOT_TRIGGERED`, `LEGAL_SCOPE_UNRESOLVED`. |
| `CoverageView` | Ba cờ độ phủ: đủ dòng kết quả / đủ bằng chứng toàn văn / kết luận đã khép. |
| Diagnostics | Bảng mã chẩn đoán theo module trên bản nháp và báo cáo. |
| `CONTEXT_LIMIT` / `CALL_LIMIT` | Hai giới hạn cấu hình khiến tiêu chí không được gửi cho LLM. |

**Slide tương ứng:** 37–39 trong [deck Công nghệ C01–C13](../business/slides/cong_nghe_va_ky_thuat_he_thong_c01_c13.pptx) · **Thời lượng gợi ý:** 5–6 phút.

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

Khi mở một báo cáo thấy nhiều dòng `INSUFFICIENT` hoặc `UNKNOWN`, hãy lần theo đúng 6 tầng sau để biết nguyên nhân nằm ở tầng nào:

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

### Tầng 6 — Giới hạn cấu hình khi chạy (§2.6)

Năm tầng trên là nguyên nhân **nghiệp vụ**. Còn một nhóm nguyên nhân **vận hành** tạo ra `UNKNOWN` trông giống hệt trên báo cáo nhưng cách xử lý khác hẳn (đổi cấu hình, không phải bổ sung hồ sơ):

| Mã trong `uncertainty_reason` / diagnostics | Nghĩa | Cách nhận biết nhanh | Cách xử lý |
|---|---|---|---|
| `OFFLINE_NO_CLIENT` | `ASSESSMENT_LLM=offline` | `model_version="NO_LLM_CALL"`, không có dòng X02 `COMPLIANCE` | Bật nhà cung cấp LLM |
| `CONTEXT_LIMIT` | Gói JSON của tiêu chí vượt `ASSESSMENT_LLM_MAX_CONTEXT_CHARS` nên không được gửi | Diagnostics `C07/CONTEXT_LIMIT`; rất ít lượt gọi X02 | Nâng trần cho phù hợp model |
| `CALL_LIMIT`, `DOCUMENT_REVIEW_CALL_LIMIT` | Hết `ASSESSMENT_LLM_MAX_CALLS` (ngân sách dùng chung giữa rà toàn văn và chấm tiêu chí) | Lý do *"Đã đạt giới hạn số criterion được gọi AI"* | Nâng ngân sách |
| `UNREGISTERED_EXTERNAL_ID`, `INVALID_REQUEST`, `TIMEOUT`, `INCOMPLETE_RESPONSE` | Phản hồi của nhà cung cấp bị backend từ chối hoặc lượt gọi lỗi | `model_version="UNAVAILABLE_PROVIDER_MODEL"` | Xem log/X02; sửa prompt/schema hoặc thử lại |
| `[MACHINE_DRAFT_REVIEW] …` | LLM đã phân tích và tự nói chưa đủ chứng cứ | `model_version` là tên model thật | Đây mới là `UNKNOWN` nghiệp vụ: bổ sung hồ sơ |

**Số đo thực tế (17/11/2026, cụm k3d local).** Ba lượt chạy trên **cùng một hợp đồng** (`HD360_001.pdf`, SHA-256 `34ac97fb…`), cùng `DRAFT_REVIEW` + `document_set_complete=true`, cùng snapshot tri thức, 124 tiêu chí:

| Lượt chạy | Cấu hình C07 | `SATISFIED` | `UNKNOWN` | `OUTSIDE_REVIEW_SCOPE` | Nguyên nhân của `UNKNOWN` | C08 `COMPLIANT` / `INSUFFICIENT` |
|---|---|---:|---:|---:|---|---:|
| `CA_UP_C668138BCD2B` | Qwen 4B local · trần ngữ cảnh 12.000 | 9 | 80 | 35 | 80 × `CONTEXT_LIMIT` | 0 / 76 |
| `CA_UP_D0FBC020C6C9` | gpt-4.1-mini · trần 80.000 · ngân sách 160 | 13 | 76 | 35 | 76 × `CALL_LIMIT` (rà toàn văn dùng hết ngân sách) | 2 / 74 |
| `CA_UP_EA117132E9D1` | gpt-4.1-mini · trần 80.000 · ngân sách 2.000 | 41 | 48 | 35 | 38 × `UNREGISTERED_EXTERNAL_ID` · 10 × model nói chưa đủ chứng cứ | 18 / 58 |

Cách đọc bảng này:

* **Engine và 8 cổng không đổi giữa ba lượt**; khác biệt đến từ model và hai giới hạn cấu hình. Gỡ một giới hạn thì giới hạn kế tiếp lộ ra — nên khi thấy hàng loạt `UNKNOWN` cùng một lý do, hãy nghi cấu hình trước.
* **35 tiêu chí `OUTSIDE_REVIEW_SCOPE` không đổi** qua cả ba lượt: phạm vi rà soát do backend quyết định, không phụ thuộc LLM.
* **9 `SATISFIED` ở lượt đầu không cần LLM** (7 × `C07_EXACT_CONTENT_V3`, 2 × `BACKEND_NUMERIC_V1`).
* Ở lượt thứ ba chỉ **10/48** `UNKNOWN` là do model tự nhận thiếu chứng cứ; 38 còn lại là phản hồi bị từ chối vì tham chiếu mã bằng chứng ngoài chưa đăng ký — việc kỹ thuật kế tiếp cần xử lý.
* **Giới hạn của số đo:** một hợp đồng, kết quả là bản nháp máy (`AI_DRAFT_PENDING_HUMAN`), chưa có người duyệt và **chưa đối chiếu Gold**. Số `SATISFIED` tăng không chứng minh các kết luận đó đúng; không dùng bảng này làm số đo độ chính xác hay suy rộng cho corpus.

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

## Hỏi – đáp khi trình bày

**Hỏi: Sao báo cáo nhiều `UNKNOWN` thế?**  
Đáp: Có hai nhóm nguyên nhân cần tách khi trả lời. (1) Nghiệp vụ: thiếu dữ kiện trong hợp đồng, chứng cứ mâu thuẫn, chưa chứng minh được vắng mặt. (2) Vận hành: LLM tắt, vượt giới hạn ngữ cảnh, hết ngân sách lượt gọi, lỗi nhà cung cấp. Nhóm (2) giảm được bằng cấu hình — xem số đo ở §2.6.

**Hỏi: Có thể ép `UNKNOWN` về Đạt/Không đạt để báo cáo gọn hơn không?**  
Đáp: Không nên. Ép nhãn là biến thiếu căn cứ thành kết luận pháp lý. Thay vào đó `UNKNOWN` được chuyển thành rủi ro loại `VERIFICATION` kèm yêu cầu bổ sung cụ thể.

**Hỏi: `coverage_complete=false` có phải pipeline bỏ sót tiêu chí?**  
Đáp: Không nhất thiết. `CoverageView` tách ba ý: đã có đủ dòng kết quả chưa, đã xác nhận phủ toàn văn chưa, và kết luận ở mức yêu cầu đã khép chưa.

**Hiểu lầm hay gặp cần tránh khi nói:**

* `UNKNOWN` ≠ `OUTSIDE_REVIEW_SCOPE` ≠ `NOT_TRIGGERED`; ba nhãn có mẫu số riêng khi chấm.
* Số đo ở §2.6 là từ vài lượt chạy thử trên một hợp đồng, không phải benchmark và không suy rộng thành tỷ lệ của hệ thống.

---

## 4. Tổng kết bộ System Deep Dive

Đến đây, bạn đã đi xuyên suốt toàn bộ kiến trúc logic của `Legal-Ai-Compliance-Checker`:
* **Từ PDF nguyên bản → Chunk giữ nguyên văn → C02/C03 có quote & SHA-256** ([Bài 03](03-document-intelligence.md))
* **Tách Nhánh A (C04 Kleene Scope + C05 Half-Open Interval & Chuyển tiếp) khỏi Nhánh B (C09 Citation)** ([Bài 04](04-scope-and-temporal-resolution.md), [Bài 05](05-citation-validation-and-retrieval.md))
* **Tìm kiếm C06 + Rà toàn văn → Chấm thuần C07 qua 8 Gates & Decimal → Tổng hợp C08 `AGG_CAN_HO_V1`** ([Bài 05](05-citation-validation-and-retrieval.md), [Bài 06](06-compliance-reasoning-and-c07-c08.md))
* **Hợp nhất C10 có provenance + Render C11 theo 22 `LIMITS` → C12 Event Overlay & C13 Export có dấu SHA-256** ([Bài 07](07-risk-and-recommendation.md), [Bài 08](08-report-generation-and-human-review.md))
* **Vận hành tin cậy qua Queue/Lease/Heartbeat & Trung thực với mọi trạng thái `UNKNOWN`/`INSUFFICIENT`** ([Bài 09](09-async-workflow-and-job-lifecycle.md), [Bài 10](10-unknown-insufficient-and-diagnostics.md)).

Quay về mục lục tổng hợp: [docs/system-guide/README.md](README.md) · [docs/README.md](../README.md).
