# 06 — Compliance Reasoning (`C07`) & Aggregation (`C08`)

> **Tài liệu thẩm quyền liên quan:** [Nhóm C — Compliance & Risk](../modules/group_c_compliance_and_risk.md) · [Criterion Verification Guide](../modules/criterion_verification_guide.md) · [Baseline v3 Draft Review Fix](../guides/baseline_v3_draft_review_fix_20261109.md)  
> **Source code trung tâm:** [`criterion_reasoner.py`](../../backend/src/legal_checker/modules/compliance/criterion_reasoner.py) · [`reviewed_observations.py`](../../backend/src/legal_checker/modules/compliance/reviewed_observations.py) · [`review_scope.py`](../../backend/src/legal_checker/modules/compliance/review_scope.py) · [`numeric_rules.py`](../../backend/src/legal_checker/modules/compliance/numeric_rules.py) · [`requirement_aggregator.py`](../../backend/src/legal_checker/modules/compliance/requirement_aggregator.py)

---

## 0. Trình bày nhanh (đọc phần này trước khi thuyết trình)

> **Một câu:** C07 chấm từng tiêu chí theo nguyên tắc “LLM đề xuất – backend kiểm chứng – engine thuần quyết định” với 8 cổng an toàn; C08 tổng hợp các tiêu chí lên mức yêu cầu theo thứ tự ưu tiên cố định.

**Hình dung đời thường.** Hình dung một phiên toà nhỏ cho mỗi tiêu chí. LLM là người nêu ý kiến (“tôi cho rằng vi phạm, bằng chứng là câu này”). Thư ký toà (backend) kiểm xem câu đó có thật trong hồ sơ không và tự tính lại các con số. Thẩm phán (engine) chỉ ra phán quyết khi đủ 8 điều kiện thủ tục; thiếu một điều kiện thì ghi “chưa đủ căn cứ” và nêu thiếu gì.

**Ba ý phải nói được:**

1. **Ba lớp tách biệt:** `LLMObservationProvider` (đề xuất) → adapter backend (kiểm quote, Decimal, tính Gates) → `criterion_reasoner.py` (thuần, tất định).
2. **8 Gates:** `reliable()` cho `SATISFIED`/`VIOLATED`; thêm `coverage_complete` + `absence_verified` mới được `MISSING`.
3. **C08 không bỏ phiếu đa số:** một tiêu chí bắt buộc `VIOLATED` là đủ `NON_COMPLIANT`; còn `UNKNOWN` thì `INSUFFICIENT`.

**Thuật ngữ dùng trong chương:**

| Thuật ngữ | Nghĩa dễ hiểu |
|---|---|
| Observation / SemanticProposal | Đề xuất của LLM: kết luận dự kiến, quote ứng viên, fact ứng viên. |
| Gates | 8 cờ kiểm chứng phải đạt trước khi chốt kết luận. |
| Finding | Nhãn ở mức tiêu chí: `SATISFIED`, `VIOLATED`, `MISSING`, `UNKNOWN`. |
| `OUTSIDE_REVIEW_SCOPE` | Ngoài chế độ rà soát đã chọn (không phải Đạt). |
| `NOT_TRIGGERED` | Nghĩa vụ có điều kiện mà điều kiện không xảy ra (không phải Đạt). |
| `AGG_CAN_HO_V1` | Đặc tả thứ tự ưu tiên tổng hợp từ tiêu chí lên yêu cầu. |

**Slide tương ứng:** 27–30 trong [deck Công nghệ C01–C13](../business/slides/cong_nghe_va_ky_thuat_he_thong_c01_c13.pptx) · **Thời lượng gợi ý:** 8–10 phút (phần quan trọng nhất).

---

## 1. Triết lý thiết kế cốt lõi: "LLM đề xuất (`Observation`), Backend kiểm chứng (`Gates`), Engine thuần quyết định (`C07`)"

Lỗi kinh điển khi dùng LLM kiểm tra tuân thủ là **tin thẳng câu trả lời JSON của model** (`"finding": "VIOLATED"`). Model có thể:
* Tự cho rằng mình đã đọc toàn bộ tài liệu dù chỉ nhìn thấy 3 đoạn top-K;
* Tính sai phép toán phần trăm (ví dụ `35%` thanh toán đợt 1 vs `30%`, hoặc so sánh `36 tháng` vs `60 tháng`);
* Kết luận vi phạm một điều khoản chỉ áp dụng nếu là *bàn giao/nghiệm thu thực tế* khi đang rà một bản *dự thảo hợp đồng trước khi ký*.

Để chặn đứng 3 nguồn lỗi đó, module `compliance/` tách làm 3 lớp hoàn toàn tách biệt:
1. **`LLMObservationProvider` (`llm_observations.py`):** Chỉ được phép sinh **`SemanticProposal`** (đề xuất kết luận, trích quote ứng viên, candidate facts) kèm giải thích ngữ nghĩa. Không được quyền gán cờ xác thực.
2. **Backend Adapters (`reviewed_observations.py`, `source_verifier.py`, `numeric_rules.py`, `review_admission.py`):** Kiểm quote nguyên văn có thật trong `C06`/chunk không, đối chiếu `Decimal` chính xác tuyệt đối, kiểm chứng facts từ nguồn C02, và tính toán **`Gates`**.
3. **Pure `criterion_reasoner.py` & `requirement_aggregator.py`:** **Không tự đọc DB, không gọi HTTP, không gọi LLM**. Chỉ nhận `ApplicableRequirement` (C05) + `RetrievalEvidence` (C06) + `Observation` đã qua adapter + `KnowledgeSnapshot` để tính ra nhãn `C07`/`C08` tất định 100%.

---

## 2. Cơ chế `Gates`: 8 ổ khóa an toàn trước khi chốt Finding `C07`

Mỗi `Observation` và `CriterionResult` mang theo đối tượng [`Gates`](../../backend/src/legal_checker/shared/contracts/reasoning.py) gồm 8 cờ boolean:

| Cờ trong `Gates` | Ý nghĩa kiểm chứng |
|---|---|
| `scope_confirmed` | Requirement từ C05 đã có `scope_status == "MATCH"`. |
| `version_resolved` | Requirement từ C05 đã chốt được `version_status == "RESOLVED"`. |
| `source_verified` | Nguồn luật trực tiếp (`source_van_ban_id`, `source_dieu_khoan_id`, `requirement_version_id`) khớp trọn vẹn trong `KnowledgeSnapshot`. |
| `evidence_validated` | Trích dẫn (`quote`, `doan_id`, `offsets`) tồn tại nguyên văn trong tài liệu nguồn và đúng chủ thể/vai trò (`subject_grounding.py`). |
| `exceptions_resolved` | Toàn bộ ngoại lệ (`ngoai_le_ap_dung`) gắn với tiêu chí đã có dữ kiện xác định là không rơi vào ngoại lệ. |
| `evidence_conflict` | **Phải là `False`** (chỉ cần phát hiện 2 điều khoản/phụ lục mâu thuẫn giá bán hay thời hạn chưa giải tỏa → giữ `UNKNOWN`!). |
| `coverage_complete` | Đã kiểm tra đủ các phần hợp đồng và phụ lục liên quan. |
| `absence_verified` | Đã chứng minh vắng mặt toàn văn (từ `FullDocumentReviewer` sạch `UNCERTAIN` & mọi trang đều có text). |

Từ đó rút ra 2 quy tắc thép trong code:
* `gates.reliable() == True` đòi hỏi **đồng thời** 5 cờ đầu là `True` **và** `not gates.evidence_conflict`. Chỉ cần 1 ổ khóa chưa mở, mọi đề xuất `SATISFIED` hoặc `VIOLATED` của LLM lập tức bị hạ về **`UNKNOWN`** kèm `uncertainty_reason`!
* `gates.missing_allowed() == True` đòi hỏi `gates.reliable()` **cộng thêm** `coverage_complete` **và** `absence_verified`. Do đó, **không thể có chuyện retrieval tìm không ra rồi kết luận bừa là `MISSING`**.

---

## 3. Phân định chế độ đánh giá (`DRAFT_CONTENT_REVIEW_V1` trong `review_scope.py`)

Đây là cơ chế trả lời trực tiếp câu hỏi thực tế của người dùng về 2 chế độ trên giao diện:
* **`DRAFT_REVIEW` (*Rà soát dự thảo trước khi ký*):** Hợp đồng chưa ký, chưa có biên bản bàn giao hay chứng từ thu tiền thực tế.
* **`FULL_TRANSACTION_EVALUATION` (*Đánh giá cả giao kết và thực hiện giao dịch*):** Xét toàn bộ cả nội dung văn bản lẫn chứng từ thực hiện giao dịch (nếu thiếu chứng từ ngoài đã đăng ký thì phải giữ `UNKNOWN`).

Hàm [`apply_review_scope()`](../../backend/src/legal_checker/modules/compliance/review_scope.py) chạy ngay sau bước `C05` để gắn nhận xét `assessment_review` mà **không làm biến dạng bản chất `scope_status`/`version_status` pháp lý gốc**:

1. **Những tiêu chí kiểm nội dung văn bản (`CONTRACT_TEXT`, `NOI_DUNG_HOP_DONG_THEO_MAU`)** → Giữ nguyên để `C07` chấm bình thường.
2. **Những tiêu chí chỉ xét việc thực hiện thực tế (`EXECUTION_ONLY`, `PERFORMANCE_WITH_DOCUMENTS`) hoặc tiêu chí hỗn hợp cần chứng từ ngoài (`EXTERNAL_MIXED`, ví dụ biên lai thanh toán, giấy phép xây dựng thực tế ngoài hợp đồng)** → Khi ở chế độ `DRAFT_REVIEW`, được đánh dấu loại trừ cục bộ với lý do bắt đầu bằng **`REVIEW_SCOPE_EXCLUDED: ...`** (hiển thị trên UI là **`OUTSIDE_REVIEW_SCOPE`**).
3. **Các tiêu chí hỗn hợp có thể kiểm tra ngay trên nội dung dự thảo (`CONTENT_BINDINGS`, ví dụ kiểm tra mức giá, ngày bàn giao dự kiến, phương thức thanh toán, thời hạn bảo hành `warranty_months`)** → Được giữ lại để rà soát ngay trên văn bản dự thảo, nhưng vẫn tách rạch ròi `evaluation_target` (đang chấm câu chữ điều khoản hay chứng từ thực tế).

> **Nguyên tắc sống còn:** `OUTSIDE_REVIEW_SCOPE` **không phải** `COMPLIANT`, `NOT_APPLICABLE`, hay `NOT_TRIGGERED`. Nó chỉ nói rõ rằng *trong chế độ rà soát dự thảo trước khi ký, hạng mục thực hiện giao dịch ngoài thực địa này nằm ngoài phạm vi kiểm tra hiện tại*.

---

## 4. Kiểm toán số học chính xác (`numeric_rules.py`) & Điều kiện phát sinh (`conditional_review.py`)

### 4.1. Tại sao cấm LLM làm toán?
Trong hợp đồng căn hộ có rất nhiều ngưỡng số học cứng:
* Thanh toán đợt đầu nhà ở HTTTL: tối đa `30%` giá trị hợp đồng (kể cả tiền đặt cọc).
* Tổng thanh toán trước khi bàn giao nhà: tối đa `70%` (hoặc `50%` nếu bên bán là doanh nghiệp có vốn đầu tư nước ngoài).
* Tổng thanh toán trước khi cấp Giấy chứng nhận (GCN): tối đa `95%`.
* Phí bảo trì phần sở hữu chung: đúng `2%` giá trị căn hộ (chưa VAT).
* Bảo hành nhà chung cư: tối thiểu `60 tháng`.

`numeric_rules.py` ép mọi phép so sánh số phải chuyển sang kiểu **`Decimal`** chính xác (tránh lỗi float `0.1 + 0.2`), đọc giá trị từ `Observation.facts` đã kiểm nguồn (`facts_verified == True`) và so sánh với quy tắc trong `quy_tac_quyet_dinh`. Nếu `C02` đọc thiếu số hoặc có 2 mức phí khác nhau trong cùng một hợp đồng (`2.090.000.000` vs `2.403.500.000` hoặc có chỗ ghi VAT chỗ không), `evidence_conflict` bật `True` → giữ `UNKNOWN`.

### 4.2. Phân biệt `NOT_TRIGGERED` với `SATISFIED` (`conditional_review.py`)
Có những nghĩa vụ pháp lý **chỉ phát sinh khi hợp đồng thỏa một điều kiện cục bộ (`LOCAL_CONDITION`)** — ví dụ:
* *"Nếu hợp đồng có quy định đặt cọc..."* (nhưng hợp đồng không thu cọc trước);
* *"Nếu các bên có thỏa thuận trọng tài..."* (nhưng hợp đồng chọn Tòa án);
* *"Nếu bên bán chậm bàn giao..."*.

Khi condition này được chứng minh là **không xảy ra (`ABSENT`)** một cách đáng tin cậy, `C07` đánh dấu loại trừ với disposition **`NOT_TRIGGERED`** (*Không phát sinh điều kiện*), thay vì chấm bừa `SATISFIED` (dễ làm phình giả tỷ lệ tuân thủ).

---

## 5. Tổng hợp lên mức Yêu cầu (`C08 Requirement Aggregation` — `AGG_CAN_HO_V1`)

Mỗi requirement family có thể có 1 đến nhiều tiêu chí con (`tieu_chi_danh_gia`). Hàm [`aggregate()`](../../backend/src/legal_checker/modules/compliance/requirement_aggregator.py) tổng hợp các `CriterionResult` thành một `RequirementResult` dựa trên bản đặc tả cố định **`AGG_CAN_HO_V1`** (`ENGINE_POLICY`, tuyệt đối không phải vote đa số!).

Thứ tự ưu tiên cứng (`POLICY_PRIORITY`):

1. **`SCOPE_OR_VERSION_UNRESOLVED → INSUFFICIENT`:** Nếu `C05` chưa `CONFIRMED` hoặc là `NOT_APPLICABLE` (sẽ được tách `excluded = True` kèm lý do `C05`).
2. **`PROVEN_VIOLATION → NON_COMPLIANT`:** Chỉ cần **ít nhất 1 tiêu chí bắt buộc `VIOLATED`** (kể cả khi tiêu chí khác cùng family đang `UNKNOWN` hoặc `SATISFIED`). Cờ `coverage_complete` vẫn phản ánh trung thực xem các tiêu chí còn lại có đủ hay đang treo.
3. **`UNKNOWN → INSUFFICIENT`:** Không có tiêu chí nào `VIOLATED`, nhưng có ít nhất 1 tiêu chí bắt buộc còn `UNKNOWN` (hoặc thiếu coverage).
4. **`ALL_MISSING → NON_COMPLIANT`:** Toàn bộ tiêu chí bắt buộc được xác minh vắng mặt toàn văn (`MISSING`).
5. **`MIXED_SATISFIED_MISSING → PARTIAL`:** Một phần đạt `SATISFIED`, phần còn lại đã chứng minh `MISSING`, và không còn `VIOLATED` hay `UNKNOWN`.
6. **`ALL_SATISFIED → COMPLIANT`:** Mọi tiêu chí bắt buộc áp dụng đều `SATISFIED` và không vướng unresolved.

| Trạng thái tổng hợp `RequirementStatus` (Pháp lý) | Khác với `assessment_disposition` (Vận hành) |
|---|---|
| `COMPLIANT`, `PARTIAL`, `NON_COMPLIANT`, `INSUFFICIENT` | `ASSESSED`, `OUTSIDE_REVIEW_SCOPE`, `NOT_TRIGGERED`, `LEGAL_SCOPE_UNRESOLVED` |

---

## 5b. Vận hành C07: nhà cung cấp LLM và hai giới hạn hay gây `UNKNOWN`

Engine và `Gates` không đổi theo model, nhưng **số tiêu chí thực sự được LLM phân tích** phụ thuộc cấu hình. Ba nhóm biến môi trường cần nắm khi chạy thật hoặc khi giải thích một báo cáo có nhiều `UNKNOWN`:

| Biến | Ý nghĩa | Hệ quả nếu đặt thấp |
|---|---|---|
| `ASSESSMENT_LLM` = `offline` \| `openai` \| `groq` \| `ollama` | Chọn client cho `LLMObservationProvider` và `FullDocumentReviewer`. Mặc định `offline`. | `offline`: tiêu chí ngữ nghĩa giữ `UNKNOWN` (`OFFLINE_NO_CLIENT`); chỉ còn `C07_EXACT_CONTENT_V3` và `BACKEND_NUMERIC_V1`. |
| `ASSESSMENT_LLM_MAX_CONTEXT_CHARS` (mặc định `80000`) | Trần kích thước gói JSON gửi cho **một** tiêu chí (tiêu chí + căn cứ luật + đoạn C06 + facts). | Gói vượt trần **không được gửi**: tiêu chí nhận `CONTEXT_LIMIT` (`model_version="NO_LLM_CALL"`). |
| `ASSESSMENT_LLM_MAX_CALLS` | Ngân sách **số lượt phân tích tiêu chí** (không phải số HTTP request) cho cả lượt chạy. | Hết ngân sách: tiêu chí còn lại nhận `CALL_LIMIT`. |
| `ASSESSMENT_LLM_BATCH_SIZE` | Số tiêu chí gộp trong một request. | Chỉ ảnh hưởng số request và độ dài prompt, không đổi cách tính ngân sách. |

Hai điểm dễ bỏ sót, đều đã gặp khi chạy thử ngày 17/11/2026:

1. **Rà toàn văn và chấm tiêu chí dùng chung một ngân sách.** `FullDocumentReviewer` tính chi phí bằng *số tiêu chí trong mỗi lô* (`self.cost += len(aliases)`), và `LLMObservationProvider` chỉ nhận phần còn lại: `max_calls = llm_max_calls - review_cost` (`workflows/integrated.py`). Hợp đồng dài (nhiều lô) × nhiều tiêu chí cần rà có thể tiêu hết ngân sách trước khi C07 phân tích được tiêu chí nào — khi đó diagnostics có `DOCUMENT_REVIEW_CALL_LIMIT` và hàng loạt `CALL_LIMIT`.
2. **Kích thước lô rà toàn văn tách khỏi trần ngữ cảnh tiêu chí.** Lô rà toàn văn tối đa `48.000` ký tự với nhà cung cấp API và `8.000` ký tự với Ollama local (`fdr_batch_cap`), để model nhỏ không bị nhồi quá nhiều tiêu chí vào một prompt.

> Cả `CONTEXT_LIMIT` lẫn `CALL_LIMIT` đều dẫn tới `UNKNOWN` **đúng nguyên tắc** (không có đề xuất thì không có kết luận), nhưng đó là `UNKNOWN` do cấu hình chứ không phải do hợp đồng thiếu dữ kiện. Cách nhận biết và số đo thực tế: [chương 10, §2.6](10-unknown-insufficient-and-diagnostics.md).

---

## Hỏi – đáp khi trình bày

**Hỏi: Nếu LLM trả lời sai hoặc bịa thì sao?**  
Đáp: Quote phải khớp nguyên văn trong đoạn nguồn; số được backend tính lại bằng `Decimal`; cổng nào chưa mở thì đề xuất bị hạ về `UNKNOWN` kèm `uncertainty_reason`. LLM không tự gán được cờ xác thực.

**Hỏi: Không có LLM thì C07 làm được gì?**  
Đáp: Các tiêu chí khớp nội dung nguyên văn (`C07_EXACT_CONTENT_V3`) và tiêu chí số học (`BACKEND_NUMERIC_V1`) vẫn chấm được. Tiêu chí cần hiểu ngữ nghĩa giữ `UNKNOWN` với lý do `OFFLINE_NO_CLIENT`.

**Hỏi: Đổi model (Qwen local → gpt-4.1-mini) thì kết luận có đổi cách ra không?**  
Đáp: Quy tắc ra kết luận không đổi vì nằm ở engine thuần và Gates. Thứ thay đổi là chất lượng đề xuất và số tiêu chí được phân tích trong giới hạn ngữ cảnh/ngân sách.

**Hiểu lầm hay gặp cần tránh khi nói:**

* `OUTSIDE_REVIEW_SCOPE` và `NOT_TRIGGERED` không được cộng vào tỷ lệ “đạt”.
* `INSUFFICIENT` là trạng thái ở mức yêu cầu (C08); `UNKNOWN` là nhãn ở mức tiêu chí (C07).

---

## 6. Đọc tiếp & Tham chiếu nhanh

* **Bước kế tiếp trong bộ Deep Dive:** [07 — Risk & Recommendation](07-risk-and-recommendation.md)
* **Đối chiếu code:**
  * [`criterion_reasoner.py`](../../backend/src/legal_checker/modules/compliance/criterion_reasoner.py) — xử lý `_rule_gate_issues`, `_exclusion`, `_type_issues`, `numeric_rules`.
  * [`review_scope.py`](../../backend/src/legal_checker/modules/compliance/review_scope.py) — chính sách `DRAFT_CONTENT_REVIEW_V1` và bản đồ `CONTENT_BINDINGS` / `EXTERNAL_MIXED`.
  * [`requirement_aggregator.py`](../../backend/src/legal_checker/modules/compliance/requirement_aggregator.py) — chính sách `AGG_CAN_HO_V1` và bảo vệ chống `excluded` sai nguyên tắc.
