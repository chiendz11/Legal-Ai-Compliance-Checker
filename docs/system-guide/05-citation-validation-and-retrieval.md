# 05 — Citation Validation (`C09`) & Retrieval (`C06`)

> **Tài liệu thẩm quyền liên quan:** [Nhóm B — Legal & Retrieval](../modules/group_b_legal_and_retrieval.md) · [Citation Identity Policy](../contracts/citation_identity_policy.json) · [Thử nghiệm phương pháp xử lý hợp đồng](../guides/legal_document_methods_trial_20261109.md) · [Rà full-text C06](../guides/hd360_followup_verification_20261108.md)  
> **Source code trung tâm:** [`modules/citation_validation/`](../../backend/src/legal_checker/modules/citation_validation/service.py) · [`modules/retrieval/service.py`](../../backend/src/legal_checker/modules/retrieval/service.py) · [`modules/compliance/document_review.py`](../../backend/src/legal_checker/modules/compliance/document_review.py)

---

## 0. Trình bày nhanh (đọc phần này trước khi thuyết trình)

> **Một câu:** Chương này gồm hai việc độc lập: C09 kiểm các văn bản mà hợp đồng tự viện dẫn (Nhánh B), và C06 tìm đoạn hợp đồng liên quan cho từng tiêu chí rồi rà toàn văn khi cần chứng minh sự vắng mặt.

**Hình dung đời thường.** C09 giống người soát phần “tài liệu tham khảo” của một bài báo: tài liệu có tồn tại không, có đúng ấn bản còn hiệu lực lúc bài được viết không. C06 giống thủ thư: tìm nhanh vài trang liên quan cho mỗi câu hỏi; nhưng khi câu hỏi là “hợp đồng có *thiếu* điều khoản X không”, thủ thư phải lật hết cuốn sách trước khi dám nói “không có”.

**Ba ý phải nói được:**

1. **C09 xét hiệu lực tại ngày ký**, không phải hôm nay; văn bản không có trong kho thì `UNKNOWN` chứ không phải `INVALID`.
2. **C06 dùng nhiều tín hiệu** (BM25, embedding, anchors, fact evidence, ngữ cảnh cấu trúc) hợp nhất bằng RRF (`RRF_K=60`).
3. **“Tìm không thấy” chưa phải “không có”:** chỉ khi rà toàn văn sạch (đủ trang, đủ chữ, không `UNCERTAIN`, không lỗi lô) mới bật `absence_verified`.

**Thuật ngữ dùng trong chương:**

| Thuật ngữ | Nghĩa dễ hiểu |
|---|---|
| `VALID` / `STALE` / `INVALID` / `UNKNOWN` | Viện dẫn hợp lệ / đã hết hiệu lực tại ngày ký / sai / chưa đủ căn cứ. |
| BM25 | Xếp hạng theo từ khoá. |
| RRF | Reciprocal Rank Fusion — cộng điểm theo thứ hạng từ nhiều nguồn tìm kiếm. |
| Reranker | Mô hình xếp lại top ứng viên (tuỳ chọn). |
| `absence_verified` | Cờ xác nhận đã chứng minh vắng mặt trên toàn văn. |

**Slide tương ứng:** 23, 25–26 trong [deck Công nghệ C01–C13](../business/slides/cong_nghe_va_ky_thuat_he_thong_c01_c13.pptx) · **Thời lượng gợi ý:** 6–7 phút.

---

## Phần 1: Nhánh B — Kiểm định Viện dẫn Hợp đồng (`C09 Citation Validation`)

### 1.1. Tại sao phải tách riêng Nhánh B và cấm nó chỉnh sửa Nhánh A?

Trong hợp đồng mua bán căn hộ, phần *"Căn cứ"* và các điều khoản thường dẫn chiếu nhiều văn bản luật. Có 3 sai lầm phổ biến nếu trộn Citation với Applicable Law:
1. Hợp đồng viết thiếu Luật KDBĐS 2023 không có nghĩa hợp đồng được miễn áp dụng Luật KDBĐS 2023.
2. Hợp đồng viết sai ngày ban hành của một Thông tư (hoặc dẫn chiếu một Bộ luật đã hết hiệu lực tại ngày ký) không tự động khiến mọi điều khoản nội dung bên dưới bị đánh dấu `VIOLATED` ở `C07` — điều khoản bảo hành hay thanh toán vẫn phải chấm theo nội dung thật của nó, còn bản thân **lỗi dẫn chiếu sai** phải được ghi nhận như một phát hiện `C09` độc lập dẫn tới Citation Risk ở `C10`.

Vì vậy, [`CatalogCitationValidator.validate()`](../../backend/src/legal_checker/modules/citation_validation/service.py) nhận đầu vào là `C03` (`CitationExtraction`) + `ContractProfile` + `KnowledgeSnapshot`, và **tạo đúng 1 bản ghi `CitationValidation` cho mỗi lần xuất hiện (`occurrence`)** của một viện dẫn trong hợp đồng.

### 1.2. Đường ống 5 bước của `C09`

```
C03 raw occurrence
  → [1. Normalizer]         Giữ raw text gốc, chuẩn hóa số hiệu/năm/loại văn bản
  → [2. Identity Validator] Khớp số hiệu (ví dụ 65/2014/QH13) hoặc numbered_anchors()
                            Mơ hồ (chỉ ghi tên+năm, không số hiệu) → giữ UNKNOWN!
  → [3. Temporal Validator] Đối chiếu ngày ký relevant_date() với quan_he_van_ban
                            (có hiệu lực tại ngày ký vs đã bị thay thế trước ngày ký?)
  → [4. Domain Validator]   Kiểm prefix/lĩnh vực (DEFAULT_DOMAIN_PREFIXES) có đúng giao dịch căn hộ không?
  → [5. Classifier]         Chốt status ∈ {VALID, STALE, INVALID, UNKNOWN} + ly_do + current_status
```

### 1.3. Những nguyên tắc tinh tế tránh "oan sai" pháp lý ở `C09`

* **Phân biệt Lịch sử (`status`) vs Hiện tại (`current_status`):** Một hợp đồng ký năm `2020` dẫn chiếu *"Luật Nhà ở 65/2014/QH13"*. Tại năm `2020`, văn bản này đang có hiệu lực hợp pháp → `status = VALID` (đối với hợp đồng lịch sử đó), nhưng trường `current_status` ghi nhận riêng là văn bản này ngày nay đã bị thay thế. Nếu hợp đồng ký năm `2025` vẫn dẫn chiếu Luật `65/2014/QH13`, tại `relevant_date = 2025` văn bản đã hết hiệu lực → `status = STALE`.
* **Không match theo kiểu tương đồng mờ cho danh tính (`NO_MATCH ≠ INVALID`):** Nếu hợp đồng dẫn một quyết định địa phương (ví dụ Quyết định phê duyệt dự án của UBND tỉnh) không nằm trong catalog `van_ban_phap_ly` cố định, C09 giữ `UNKNOWN` (kèm ghi nhận `NO_MATCH_IN_PINNED_CATALOG` trong bài toán đánh giá), **tuyệt đối không kết luận `INVALID`**, vì không nằm trong catalog pin không chứng minh văn bản đó không tồn tại ngoài đời.
* **Cờ `finding_verified`:** Chỉ bật `True` khi văn bản được định danh `MATCHED`, extraction không ở trạng thái mơ hồ, cả `temporal.status` và `domain_status` khác `UNKNOWN`, và văn bản trong catalog đã có đủ cờ `identity_verified`, `temporal_verified`, `domain_verified`.

---

## Phần 2: Truy xuất Bằng chứng (`C06 Retrieval`) & Rà Toàn Văn Có Chọn Lọc

### 2.1. Bài toán thực tế của Retrieval trên hợp đồng Việt Nam

Một hợp đồng mua bán căn hộ điển hình dài 35–80 trang (có ca lên tới 166 trang) và cần kiểm hàng trăm tiêu chí (`tieu_chi_danh_gia`). Chúng ta không thể nhồi cả 80 trang hợp đồng vào prompt của từng tiêu chí một (vừa chậm, tốn token, vừa dễ mất tập trung ngữ cảnh); nhưng nếu chỉ tìm Top-3 đoạn giống câu chữ tiêu chí nhất thì lại vấp 3 lỗi chết người:
1. Đoạn hợp đồng ghi *"Theo Phụ lục 02 đính kèm"* — câu trả lời thực sự lại nằm ở bảng giá cuối hợp đồng.
2. Khoản ngắn chỉ ghi *"3. Thực hiện trong vòng 15 ngày."* — thiếu tiêu đề Điều (*"ĐIỀU 9. BẢO HÀNH NHÀ Ở"*) nên BM25 trượt hoàn toàn.
3. Top-K không ra kết quả không chứng minh được rằng điều khoản đó **vắng mặt (`MISSING`)** trong toàn bộ 60 trang.

### 2.2. Kiến trúc `HybridRetrievalService` (`retrieval/service.py`)

Hệ thống giải quyết 3 vấn đề trên bằng quy trình đa tín hiệu cho từng criterion (bỏ qua family `NOT_APPLICABLE`, vẫn truy xuất cho family `UNKNOWN` có `candidate_version`):

1. **Câu truy vấn thuần (`search_query`):** Chỉ dùng đúng `criterion["noi_dung"]`. Kết quả thực nghiệm trên tập DEV cho thấy việc ghép thêm trường mô tả *"Hồ sơ liên quan / bằng chứng cần thiết"* vào query làm **tụt Recall@3 và Recall@10** vì từ khóa chung chung gây nhiễu.
2. **Bơm ngữ cảnh đường dẫn cấu trúc (`path_context`):** Rút gọn `Hợp đồng/ĐIỀU 9. BẢO HÀNH NHÀ Ở/Khoản 5` thành `ĐIỀU 9. BẢO HÀNH NHÀ Ở` để ghép vào nội dung chunk khi đánh index (khắc phục lỗi khoản ngắn thiếu từ khóa chủ đề).
3. **Kết hợp đa tín hiệu với Reciprocal Rank Fusion (`RRF_K = 60`):**
   * `BM25Index` (tìm kiếm từ khóa có tokenize tiếng Việt/ký tự pháp lý).
   * `EmbeddingIndex` (tùy chọn tìm kiếm ngữ nghĩa).
   * `anchored_chunks` (`anchors.py`): Neo trực tiếp những chunk nằm ở Điều/Mục thường chứa chủ đề tương ứng.
   * `fact_evidence` (`fact_evidence.py`): Nếu tiêu chí nhắc tới một field đã được `C02` trích xuất (như `warranty_months`, `gia_ban`, `dien_tich`), đưa thẳng chunk chứng cứ của `C02` lên đầu bảng xếp hạng!
   * `structural_context` (`structural_context.py`): Kéo kèm đoạn cha/anh em kế cận khi một đoạn dẫn chiếu sang mục liền kề.
4. **Cross-Encoder Reranker & Lọc chọn `duoc_chon`:** Có thể sắp xếp lại top `rerank_k` bằng `CrossEncoderReranker`, sau đó chọn `select_k` ứng viên vượt ngưỡng `min_rerank_score` (hoặc `min_relative_score`) **và** đạt tỷ lệ phủ âm tiết `term_coverage() >= min_term_coverage`.

### 2.3. Selective Full-Document Review (`FullDocumentReviewer` — cầu nối giữa C06 và C07)

Đây là điểm phân biệt hệ thống này với mọi pipeline RAG thông thường:

```
C06 HybridRetrievalService (Top-K nhanh cho 100% tiêu chí)
        │
        ├── Tiêu chí tìm thấy bằng chứng rõ ràng trong Top-K ──► Đưa thẳng vào C07
        │
        └── Tiêu chí nhạy cảm vắng mặt (MANDATORY_CONTENT chưa thấy / PROHIBITED_CLAUSE)
                  │
                  ▼
      [RetrievalRefinementService / FullDocumentReviewer]
      1. Chia TOÀN BỘ active chunks thành các batch ≤ 48.000 ký tự (_groups)
         giữ lại 1 chunk gối đầu ở ranh giới cấu trúc/trang để không đứt mạch.
      2. Prompt `C07_FULL_DOCUMENT_REVIEW_V7` rà đủ ma trận (mọi batch × mọi criterion cần xét).
      3. Thu về `DocumentReviewArtifact`: từng ô đánh dấu PRESENT / ABSENT / UNCERTAIN.
      4. Bổ sung các chunk mới phát hiện vào C06 (refined C06) trước khi chấm C07!
```

**Vì sao làm vậy?**
* Nếu tìm Top-K ban đầu bỏ sót một câu ngoại lệ nằm tít ở Phụ lục 3, bước `FullDocumentReviewer` sẽ lôi nó lên đưa vào `C06` chính thức.
* Chỉ khi **tất cả các batch phủ 100% số trang**, **mọi trang đều đọc được chữ**, **không có ô nào trả về `UNCERTAIN` hoặc lỗi batch**, thì backend mới được phép bật cờ `gates.absence_verified = True` để C07 hợp pháp kết luận `MISSING` (hoặc xác nhận không vi phạm điều khoản cấm). Nếu chỉ một batch bị timeout hoặc một trang không đọc được chữ, `absence_verified` giữ `False` và C07 giữ **`UNKNOWN`**.

---

## Hỏi – đáp khi trình bày

**Hỏi: Hợp đồng dẫn luật đã hết hiệu lực thì các điều khoản có bị coi là vi phạm không?**  
Đáp: Không tự động. C09 tạo một phát hiện viện dẫn riêng (`STALE`) và C10 biến nó thành rủi ro loại `CITATION`. Điều khoản nội dung vẫn được C07 chấm theo nội dung thật của nó.

**Hỏi: Sao không nhét cả hợp đồng vào prompt cho chắc?**  
Đáp: Hợp đồng 35–80 trang (có ca 166 trang) × hàng trăm tiêu chí thì quá chậm và tốn. Hệ thống tìm top-K cho mọi tiêu chí, và chỉ rà toàn văn cho nhóm tiêu chí mà sự vắng mặt là điều cần chứng minh.

**Hỏi: Một lô rà toàn văn bị timeout thì sao?**  
Đáp: `absence_verified` giữ `false`, C07 giữ `UNKNOWN` cho các tiêu chí liên quan. Hệ thống không suy ra “không có” từ một lần rà chưa trọn.

**Hiểu lầm hay gặp cần tránh khi nói:**

* Rà toàn văn dùng chung ngân sách lượt gọi với C07 (xem [chương 06](06-compliance-reasoning-and-c07-c08.md) và [chương 10](10-unknown-insufficient-and-diagnostics.md)); đặt ngân sách thấp sẽ làm C07 hết lượt.
* Đoạn nằm ngoài tập đã chấm của Gold là `UNJUDGED`, không mặc định là sai.

---

## 3. Đọc tiếp & Tham chiếu nhanh

* **Bước kế tiếp trong bộ Deep Dive:** [06 — Compliance Reasoning & C07/C08](06-compliance-reasoning-and-c07-c08.md)
* **Đối chiếu code:**
  * [`CatalogCitationValidator`](../../backend/src/legal_checker/modules/citation_validation/service.py) — đường ống Nhánh B (`validate_identity → validate_temporal → validate_domain → classify`).
  * [`HybridRetrievalService`](../../backend/src/legal_checker/modules/retrieval/service.py) — `RRF_K`, `path_context`, `fact_evidence`, `term_coverage`.
  * [`FullDocumentReviewer`](../../backend/src/legal_checker/modules/compliance/document_review.py) — ma trận `DocumentReviewArtifact` và thuật toán batch gối đầu.
