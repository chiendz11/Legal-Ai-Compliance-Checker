# 07 — Risk (`C10`) & Recommendation (`C11`)

> **Tài liệu thẩm quyền liên quan:** [Nhóm C — Compliance & Risk](../modules/group_c_compliance_and_risk.md) · [Chuẩn hóa báo cáo và C11 bindings](../guides/report_consistency_and_llm_efficiency_20261109.md) · [Report Presentation](../contracts/report_presentation.md)  
> **Source code trung tâm:** [`risks/aggregator.py`](../../backend/src/legal_checker/modules/risks/aggregator.py) · [`risks/compliance_mapper.py`](../../backend/src/legal_checker/modules/risks/compliance_mapper.py) · [`risks/citation_mapper.py`](../../backend/src/legal_checker/modules/risks/citation_mapper.py) · [`recommendations/generator.py`](../../backend/src/legal_checker/modules/recommendations/generator.py) · [`recommendations/rendering.py`](../../backend/src/legal_checker/modules/recommendations/rendering.py)

---

## 1. Module Rủi ro (`C10`): Hợp nhất hai nhánh & Khóa chống "JOIN lỏng"

### 1.1. Hai nguồn rủi ro độc lập chảy vào một đầu ra `RiskResult`

Hàm [`aggregate_risks()`](../../backend/src/legal_checker/modules/risks/aggregator.py) nhận kết quả từ hai nhánh song song:
* **Nhánh A (`compliance_risks()`):** Sinh rủi ro từ từng `CriterionResult` (`C07`) có `finding` là `VIOLATED`, `MISSING`, hoặc `UNKNOWN` (trừ trường hợp đã bị `excluded`). Rủi ro mang `risk_type = "COMPLIANCE"` hoặc `"VERIFICATION"` (khi finding là `UNKNOWN`).
* **Nhánh B (`citation_risks()`):** Sinh rủi ro từ từng `CitationValidation` (`C09`) có `status` là `STALE`, `INVALID`, hoặc `UNKNOWN`. Rủi ro mang `risk_type = "CITATION"` hoặc `"VERIFICATION"`.

Mỗi `RiskResult` mang `RiskSource` bắt buộc (`single_source` — truy ngược được đúng về 1 `ket_qua_id` của C07 **hoặc** 1 `finding_id` của C09, kèm `legal_basis_ids` và `severity` từ catalog, không bịa severity).

### 1.2. Tại sao cần `validate_findings()` và `PRODUCTION_GATE`?

Trước khi tạo bất kỳ rủi ro nào, [`compliance_mapper.py`](../../backend/src/legal_checker/modules/risks/compliance_mapper.py) và [`citation_mapper.py`](../../backend/src/legal_checker/modules/risks/citation_mapper.py) thực hiện một chuỗi kiểm tra toàn vẹn cực kỳ chặt:

1. **Chống ghép nhầm finding của Run khác / Snapshot khác:** `validate_findings()` kiểm từng phần tử `CriterionResult`:
   * `ca_id` và `lan_chay_id` phải khớp `request.ca_id` và `request.run_id`;
   * `tieu_chi_snapshot_json` phải khớp với định nghĩa tiêu chí và `knowledge_snapshot_sha256` của run hiện tại;
   * `hop_dong_id` phải khớp hợp đồng của payload (chặn rò rỉ chéo giữa 2 hợp đồng cùng case);
   * `legal_basis_ids` chỉ được chứa ID văn bản/điều khoản/version có trong `KnowledgeSnapshot` đã pin.
   * **Bài học thực tế:** Nhờ bước kiểm này, hệ thống triệt tiêu hoàn toàn lỗi *"JOIN lỏng trong SQL theo `ca_id` dẫn tới ghép nhầm finding của lần chạy cũ vào báo cáo mới"*.
2. **Kiểm soát phát biểu rủi ro trên Nhánh B (`STRUCTURAL_GUARDS` & `PRODUCTION_GATE`):**
   * `no_automatic_compliance_effect`: Rủi ro citation không bao giờ được tự động đánh hỏng trạng thái tuân thủ nội dung C07/C08.
   * `db_no_match_alone_is_not_invalid`: Không tìm thấy số hiệu trong DB không đủ để biến thành rủi ro "viện dẫn luật giả/vô hiệu" — chỉ được tạo `VERIFICATION` ở mức yêu cầu xác minh.
   * `current_expiry_alone_is_not_trigger`: Một văn bản hết hiệu lực ở thời điểm hiện tại nhưng còn hiệu lực vào ngày ký hợp đồng cũ không tự động kích hoạt rủi ro `STALE`.
3. **Khử trùng lặp tất định (`deduplicate`):** Nếu nhiều quy tắc cùng bắn ra cho cùng một nguồn lỗi và mức nghiêm trọng, `deduplicate()` gộp ổn định theo khóa nghiệp vụ để báo cáo không bị phình số lượng rủi ro giả tạo.

---

## 2. Module Khuyến nghị (`C11`): Template Engine Có Kỷ Luật vs LLM Tự Viết

### 2.1. Tại sao `C11` KHÔNG dùng LLM viết tự do?

Nếu cho LLM tự viết lời khuyên pháp lý kiểu *"Bên Bán là Công ty ABC cần sửa ngay mức thanh toán đợt 1 xuống 25% và thay thế Luật 2014 bằng..."*, LLM rất dễ:
* Tuyên bố tự động hợp đồng **"vô hiệu"** hoặc tự áp **mức phạt hành chính** ngoài thẩm quyền;
* Tự bịa tên công ty, số tài khoản, ngày thay thế hoặc con số mới (ví dụ tự ý khuyên `25%` thay vì nêu khung trần luật định `30%`);
* Dùng lại câu sửa lỗi thay cho yêu cầu xác minh khi bản thân hệ thống mới chỉ ở trạng thái `UNKNOWN`.

Vì vậy, [`recommendations/generator.py`](../../backend/src/legal_checker/modules/recommendations/generator.py) là một **Deterministic Template Engine** bị ràng buộc bởi tập 22 giới hạn **`LIMITS`**, nổi bật gồm:
* `no_auto_invalidity_or_fine`: Không tự kết luận vô hiệu hay phạt tiền.
* `no_invented_names_dates_accounts`: Không tự bịa tên bên, ngày tháng, số tài khoản.
* `unknown_is_verification_not_violation`: Rủi ro sinh từ `UNKNOWN` chỉ được phép sinh khuyến nghị hành động thuộc nhóm **`VERIFICATION_ACTIONS`** (`VERIFY`, `VERIFY_REFERENCE`, `REQUEST_VERIFICATION`, `REQUEST_EVIDENCE`), tuyệt đối không sinh **`REMEDY_ACTIONS`** (`ADD`, `AMEND_OR_PERFORM_CORRECTIVE_ACTION`, `CORRECT_REFERENCE`) như thể đã chứng minh vi phạm!
* `recommendation_null_if_satisfied`: Đã `SATISFIED` thì không sinh khuyến nghị thừa.
* `human_review_required`: Mọi khuyến nghị chỉ là đề xuất hỗ trợ người rà soát.

### 2.2. Cách hoạt động của Slot Binding & Vệ sinh ngôn ngữ trình bày (`rendering.py`)

Trước đây, nhiều mẫu khuyến nghị để thô các placeholder dạng `[nguyên văn]` hoặc `[thông tin/bằng chứng cụ thể còn thiếu]` gây cảm giác "lộ code debug" trên giao diện. Hệ thống khắc phục triệt để bằng chuỗi hàm trong [`rendering.py`](../../backend/src/legal_checker/modules/recommendations/rendering.py) và [`generator.py`](../../backend/src/legal_checker/modules/recommendations/generator.py):

1. **Named Slot Formatting an toàn (`_render()`):** Kiểm tra chặt bằng `string.Formatter().parse()`, **chỉ cho phép tên field hợp lệ** (`[a-zA-Z_][a-zA-Z0-9_]*`), cấm mọi format spec hay truy cập thuộc tính kiểu `{obj.__class__}` (chống template injection), và nếu thiếu bất kỳ biến bắt buộc nào thì từ chối render thay vì in ra chuỗi lỗi hay giá trị `None`.
2. **`bind_draft_slots()`:** Thay thế tường minh các slot tiếng Việt đã đăng ký trong `SLOTS`:
   * `[nguyên văn]` ← lấy qua `observed_quote(source)` từ trích dẫn nguyên văn đã chứng thực trong `evidence` (hoặc `observed_title` ở C09).
   * `[thông tin/bằng chứng cụ thể còn thiếu]` ← lấy qua `verification_request(source)` từ `uncertainty_reason` hoặc thông điệp riêng theo `reason_code` (ví dụ `NAME_ONLY_VERSION_IDENTITY_AMBIGUOUS` → yêu cầu cung cấp *"năm ban hành hoặc số hiệu, cùng bản nguồn hoặc dẫn chiếu đủ để định danh phiên bản luật"*).
3. **Liên kết chặt với Risk:** Mỗi `Recommendation` lưu `ket_qua_rui_ro_id` để giao diện luôn hiển thị song song: *Phát hiện (C07/C09) → Rủi ro (C10) → Hành động khuyến nghị (C11) → Quote PDF gốc*.

---

## 3. Đọc tiếp & Tham chiếu nhanh

* **Bước kế tiếp trong bộ Deep Dive:** [08 — Report Generation & Human Review](08-report-generation-and-human-review.md)
* **Đối chiếu code:**
  * [`aggregate_risks()`](../../backend/src/legal_checker/modules/risks/aggregator.py) — điểm hợp nhất `compliance_risks + citation_risks`.
  * [`validate_findings()`](../../backend/src/legal_checker/modules/risks/compliance_mapper.py) — rào chắn provenance C07 → C10.
  * [`recommend()`](../../backend/src/legal_checker/modules/recommendations/generator.py) & [`bind_draft_slots()`](../../backend/src/legal_checker/modules/recommendations/rendering.py) — quy tắc 22 `LIMITS` và render sạch slot tiếng Việt.
