# 07 — Risk (`C10`) & Recommendation (`C11`)

> **Tài liệu thẩm quyền liên quan:** [Nhóm C — Compliance & Risk](../modules/group_c_compliance_and_risk.md) · [Chuẩn hóa báo cáo và C11 bindings](../guides/report_consistency_and_llm_efficiency_20261109.md) · [Report Presentation](../contracts/report_presentation.md)  
> **Source code trung tâm:** [`risks/aggregator.py`](../../backend/src/legal_checker/modules/risks/aggregator.py) · [`risks/compliance_mapper.py`](../../backend/src/legal_checker/modules/risks/compliance_mapper.py) · [`risks/citation_mapper.py`](../../backend/src/legal_checker/modules/risks/citation_mapper.py) · [`recommendations/generator.py`](../../backend/src/legal_checker/modules/recommendations/generator.py) · [`recommendations/rendering.py`](../../backend/src/legal_checker/modules/recommendations/rendering.py)

---

## 0. Trình bày nhanh (đọc phần này trước khi thuyết trình)

> **Một câu:** C10 gộp rủi ro từ hai nhánh thành một danh sách, mỗi rủi ro truy ngược về đúng một nguồn; C11 sinh khuyến nghị bằng template tất định, và LLM (nếu bật) chỉ được diễn đạt lại câu chữ dưới sự kiểm soát của validator.

**Hình dung đời thường.** C10 giống người tổng hợp biên bản từ hai tổ kiểm tra: mỗi dòng phải ghi rõ do tổ nào phát hiện, ở hồ sơ nào, không được chép nhầm biên bản của đợt kiểm tra trước. C11 giống mẫu công văn điền sẵn: nội dung pháp lý cố định, chỉ điền dữ kiện có thật. Có thể nhờ biên tập viên chuốt câu, nhưng nếu bản chuốt làm mất hoặc đổi một con số, một tên luật hay một câu trích thì dùng lại nguyên bản.

**Ba ý phải nói được:**

1. **Hai nguồn rủi ro:** từ C07 (`VIOLATED`/`MISSING`/`UNKNOWN`) và từ C09 (`STALE`/`INVALID`/`UNKNOWN`); `UNKNOWN` thành rủi ro loại `VERIFICATION`.
2. **`validate_findings()` chống ghép nhầm:** khớp `ca_id`, `run_id`, `hop_dong_id` và mã băm snapshot.
3. **C11 có 22 `LIMITS`:** không tự tuyên vô hiệu/phạt, không bịa tên/ngày/số; `UNKNOWN` chỉ được sinh hành động xác minh.

**Thuật ngữ dùng trong chương:**

| Thuật ngữ | Nghĩa dễ hiểu |
|---|---|
| `RiskSource` | Con trỏ về đúng một kết quả C07 hoặc một phát hiện C09. |
| `VERIFICATION` | Loại rủi ro “cần xác minh”, sinh từ kết quả chưa biết. |
| Template Engine | Bộ sinh khuyến nghị tất định từ mẫu đã ghim trong kho tri thức. |
| Personalization | Lớp tuỳ chọn cho LLM diễn đạt lại (`C11_PERSONALIZATION=off|ollama|openai`). |
| Anchor / mỏ neo | Số tiền, %, ngày, số hiệu văn bản, câu trích… phải được giữ nguyên. |

**Slide tương ứng:** 32–33 trong [deck Công nghệ C01–C13](../business/slides/cong_nghe_va_ky_thuat_he_thong_c01_c13.pptx) · **Thời lượng gợi ý:** 4–5 phút.

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

### 2.3. Hybrid Recommendation: Template Engine + LLM Personalization (`personalization/`)

Từ nền tảng Template Engine xác định, C11 hỗ trợ thêm lớp cá thể hóa diễn đạt **tùy chọn** (`C11_PERSONALIZATION=ollama` hoặc `openai`, mặc định `off`):

1. **Template Engine luôn chạy trước và nắm quyền quyết định:** `generator.py` tạo trọn vẹn khuyến nghị chuẩn hóa (mapping `ALL`, `loai_hanh_dong`, `uu_tien`, `evidence_ids`, `legal_basis_ids`, 22 `LIMITS`). Qwen không bao giờ được chọn template hay sửa metadata pháp lý.
2. **Local Qwen chỉ viết lại câu chữ diễn đạt:** [`OllamaRecommendationClient`](../../backend/src/legal_checker/modules/recommendations/personalization/client.py) xác nhận `qwen3.5:9b-q4_K_M` và lấy digest thực qua `/api/tags`, gọi tuần tự `/api/chat` (`C11_PERSONALIZATION_V1`, JSON schema strict `PersonalizedRecommendation`) trên payload tối thiểu của khuyến nghị đó (không gửi cả PDF hay Knowledge DB) và ghi audit X02 (`module="C11"`, `provider="OLLAMA_LOCAL"`).
3. **Backend Validator chặn mọi ảo giác trước khi thay văn bản:** [`validate_personalized_output()`](../../backend/src/legal_checker/modules/recommendations/personalization/validator.py) trích xuất và đối chiếu chéo toàn bộ anchor (số tiền, `%`, ngày tháng, ngưỡng, số hiệu/tên văn bản, quote nguyên văn, thực thể/tài khoản, checklist/dự thảo); chặn phát ngôn vô hiệu/chế tài/tăng ưu tiên; và chặn tuyệt đối việc biến `UNKNOWN`/`VERIFICATION` thành kết luận vi phạm hay yêu cầu sửa chữa.
4. **Fallback an toàn (`TEMPLATE_ENGINE_FALLBACK`):** Mọi lỗi Ollama, timeout, digest sai, hết ngân sách (`C11_LLM_MAX_CALLS`), audit DB lỗi hoặc output bị validator reject đều tự động rơi về nguyên văn `noi_dung` của Template Engine kèm `model_version="TEMPLATE_ENGINE_FALLBACK"`, `prompt_version="C11_PERSONALIZATION_V1"` và mã diagnostics (`C11_PERSONALIZATION_REJECTED`, `C11_PERSONALIZATION_FALLBACK`, ...). `review_status` vẫn luôn là `PENDING`.
5. **Tuỳ chọn nhà cung cấp API (`C11_PERSONALIZATION=openai`):** [`OpenAIRecommendationClient`](../../backend/src/legal_checker/modules/recommendations/personalization/openai_client.py) dùng lại client Responses API chung (schema `strict`, `store=false`) và ghi audit X02 với `module="C11"`, `provider="OPENAI"`. Prompt, validator và fallback **giống hệt** đường Ollama; lỗi nhà cung cấp được ánh xạ thành `C11_<mã lỗi>` rồi rơi về template. Lưu ý kỹ thuật: service truyền cả `RecommendationRequest` (lớp con của `Context`) cho client, nên adapter phải rút về đúng các trường `Context` trước khi gọi client chung — thiếu bước này mọi lượt gọi sẽ thất bại trước khi tới API và hiện thành `C11_MODEL_UNAVAILABLE` không kèm dòng audit (lỗi đã sửa ngày 17/11/2026, có test hồi quy).
6. **Hiện trạng chất lượng diễn đạt lại (số đo chạy thử 17/11/2026, một hợp đồng, khuyến nghị sinh từ `UNKNOWN`):** gần như mọi bản diễn đạt lại đều bị validator loại bằng `C11_ANCHOR_MISMATCH` — 78/79 lượt với `qwen3:4b` local; 76/76 và 48/48 lượt ở hai lần chạy với `gpt-4.1-mini`. Khi lần nguyên nhân trên mẫu thật:
   * **Một lỗi của chính validator (đã sửa, có test hồi quy):** `_ENTITY_RE` không có ranh giới từ và chạy không phân biệt hoa thường, nên cụm văn xuôi như *"không đầy đủ"* bị đọc thành thực thể *"ông đầy đủ"* → `Fabricated entity or identity detected` trên 6/6 mẫu đầu. Bản sửa yêu cầu từ chỉ vai trò (`ông`, `bà`, `công ty`…) phải đứng đầu từ và tên theo sau phải viết hoa.
   * **Sau khi sửa, thử lại 12 mẫu vẫn chưa mẫu nào được chấp nhận:** 4 mẫu model làm rơi số hiệu văn bản (`Original legal code dropped`), 1 mẫu làm rơi một đại lượng, và 6 mẫu bị `Fabricated legal instrument detected` trên các cụm từ chung như *"pháp luật chuyên ngành liên quan"* — dấu hiệu mẫu nhận diện tên luật còn rộng (chưa đổi, cần rà cùng người phụ trách C11).
   * **Kết luận vận hành:** lớp an toàn hoạt động đúng (không câu nào của LLM lọt vào báo cáo), nhưng lợi ích của personalization cho nhóm khuyến nghị này hiện gần như bằng 0. Hướng xử lý hợp lý là siết prompt (giữ nguyên số hiệu, không thêm cụm "pháp luật …") hoặc bỏ qua personalization cho mục `UNKNOWN`, thay vì nới validator tuỳ tiện.

---

## Hỏi – đáp khi trình bày

**Hỏi: Sao không để LLM viết khuyến nghị cho tự nhiên?**  
Đáp: Vì rủi ro pháp lý: model dễ tuyên bố vô hiệu, bịa tên/số tài khoản, hoặc tự đề xuất con số mới. Nội dung pháp lý do template quyết định; LLM chỉ chỉnh câu chữ và phải qua validator.

**Hỏi: Validator loại bản diễn đạt lại thì người dùng thấy gì?**  
Đáp: Thấy nguyên văn khuyến nghị của template, kèm `model_version="TEMPLATE_ENGINE_FALLBACK"` và mã chẩn đoán. Không có câu nào của LLM lọt vào báo cáo.

**Hỏi: Tỷ lệ bản diễn đạt lại được chấp nhận hiện là bao nhiêu?**  
Đáp: Thấp. Trong các lượt chạy thử ngày 17/11/2026 trên một hợp đồng, gần như toàn bộ bản diễn đạt lại (cả Qwen 4B local lẫn gpt-4.1-mini) bị loại với `C11_ANCHOR_MISMATCH`. Một phần do lỗi regex của validator (đã sửa), phần còn lại do model làm rơi số hiệu văn bản và mẫu nhận diện tên luật còn rộng — chi tiết ở §2.3 mục 6.

**Hiểu lầm hay gặp cần tránh khi nói:**

* Rủi ro viện dẫn (C09) không tự làm đổi trạng thái tuân thủ nội dung (C07/C08).
* Khuyến nghị cho mục `UNKNOWN` là “yêu cầu xác minh/bổ sung chứng cứ”, không phải “yêu cầu sửa hợp đồng”.

---

## 3. Đọc tiếp & Tham chiếu nhanh

* **Bước kế tiếp trong bộ Deep Dive:** [08 — Report Generation & Human Review](08-report-generation-and-human-review.md)
* **Đối chiếu code:**
  * [`aggregate_risks()`](../../backend/src/legal_checker/modules/risks/aggregator.py) — điểm hợp nhất `compliance_risks + citation_risks`.
  * [`validate_findings()`](../../backend/src/legal_checker/modules/risks/compliance_mapper.py) — rào chắn provenance C07 → C10.
  * [`recommend()`](../../backend/src/legal_checker/modules/recommendations/generator.py) & [`bind_draft_slots()`](../../backend/src/legal_checker/modules/recommendations/rendering.py) — quy tắc 22 `LIMITS` và render sạch slot tiếng Việt.
  * [`RecommendationPersonalizationService`](../../backend/src/legal_checker/modules/recommendations/personalization/service.py) & [`validate_personalized_output()`](../../backend/src/legal_checker/modules/recommendations/personalization/validator.py) — cá thể hóa Qwen local có kiểm chứng và fallback về Template Engine.
