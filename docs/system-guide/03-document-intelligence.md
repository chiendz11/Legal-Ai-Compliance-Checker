# 03 — Document Intelligence (`C01`, Chunks, `C02`, `C03`)

> **Tài liệu thẩm quyền liên quan:** [Nhóm A — Document Intelligence](../modules/group_a_document_intelligence.md) · [Local LLM Extraction](../modules/documents_local_llm.md) · [Luồng Dữ liệu & Lưu trữ PDF](../architecture/data_flow_and_storage.md) · [Source-Observed Baseline](../contracts/source_observed_extraction_baseline.md)  
> **Source code trung tâm:** [`intake.py`](../../backend/src/legal_checker/modules/documents/intake.py) · [`parser.py`](../../backend/src/legal_checker/modules/documents/parser.py) · [`chunker.py`](../../backend/src/legal_checker/modules/documents/chunker.py) · [`profile_extractor.py`](../../backend/src/legal_checker/modules/documents/profile_extractor.py) · [`semantic_extractor.py`](../../backend/src/legal_checker/modules/documents/semantic_extractor.py) · [`citation_extractor.py`](../../backend/src/legal_checker/modules/documents/citation_extractor.py) · [`service.py`](../../backend/src/legal_checker/modules/documents/service.py)

---

## 1. Tại sao Document Intelligence là lớp nền sống còn?

Trong một hệ thống kiểm tra tuân thủ có truy vết (auditable compliance), mọi kết luận ở bước C07 hay C10 đều phải trả lời được câu hỏi: **"Con số hoặc điều khoản này nằm ở trang mấy, chunk nào, từ ký tự nào tới ký tự nào trong PDF?"**. Nếu ngay ở bước đọc tài liệu ban đầu:
* Khoảng trắng bị chuẩn hóa tùy tiện làm lệch offset;
* Bảng mục lục (TOC) bị nhận nhầm là tiêu đề Điều thật làm gãy ranh giới chunk;
* Giá trị tiền tệ, diện tích bị LLM tự đoán hoặc gán nhầm giữa diện tích thông thủy căn hộ và diện tích thửa đất;

thì toàn bộ pipeline phía sau (`C04`–`C13`) sẽ sai dây chuyền. Do đó, Document Intelligence được thiết kế theo triết lý **bảo toàn nguyên văn (`verbatim`) và không bịa dữ kiện (`no fabricated values`)**.

---

## 2. Bước `C01` Intake & Kiểm toàn vẹn nguồn (`SourceStorage`)

Trước khi bóc một ký tự nào từ PDF, hệ thống đi qua 2 lớp bảo vệ:

1. **Xác thực `AssessmentCase` (`C01`):** `IntakeService.register()` (`intake.py`) và `validate_case()` (`handoffs.py`) cố định `ca_id`, `hop_dong_id`, `tenant_id`, `source` (URL hoặc upload ID, MIME type, **`sha256`**) và `assessment_context` (chọn chế độ `review_mode`: `DRAFT_REVIEW` hay `FULL_TRANSACTION_EVALUATION`, `loai_moc_ap_dung`, `moc_ap_dung`).
   * **Nguyên tắc bảo mật quan trọng:** Chế độ đánh giá (`review_mode`) chỉ được quyền do caller truyền vào ở `C01` và lưu DB. **Bản thân nội dung văn bản PDF không bao giờ có quyền tự bật/tắt `review_mode`** (chống prompt injection giấu trong PDF).
2. **Đọc bytes & khớp SHA-256 (`PdfDocumentIntelligence.run()`):**
   * `SourceStorage.read()` (qua `LocalUploadStorage`, `CachedHttpSourceStorage` hoặc `RoutingSourceStorage`) tải bytes thật và kiểm tra định dạng (`sniff_mime_type`, PDF header). Không tự fallback sang file sidecar text bên ngoài khi chạy thật.
   * `PdfTextReader.extract()` đọc từng trang PDF, tạo danh sách `DocumentPage` và tính lại `source_sha256`. Nếu khác `case.source.sha256`, lập tức ném **`SourceMismatchError`** và dừng — không trích xuất trên tài liệu bị tráo đổi.
   * Ghi nhận **`DocumentReadCoverage`**: `valid_pages`, tỷ lệ trang đọc được chữ, và cờ **`all_pages_have_text`** (rất quan trọng để C07 biết có được phép kết luận `MISSING` hay không). Với PDF scan không có lớp text hoặc DOCX, module `ocr.py` / parser DOCX hiện giữ giới hạn rõ ràng, không giả vờ đọc đủ.

---

## 3. Thuật toán Chunking bảo toàn cấu trúc & Offset (`chunker.py`)

Khác với cách chia chunk ngây thơ *"cắt đều mỗi 1000 ký tự, trượt 200 ký tự"* (dễ cắt đôi câu điều kiện hoặc mất tên Điều), [`chunk_document()`](../../backend/src/legal_checker/modules/documents/chunker.py) (version `structural-sentences-v2`) đi qua chuỗi xử lý 4 tầng:

### Bước 1: Ghép trang và giữ bảng ánh xạ vị trí (`join_pages`)
Ghép text tất cả các trang thành một chuỗi liên tục lớn, đồng thời lưu vị trí bắt đầu/kết thúc của từng trang để bất kỳ cặp `(global_start, global_end)` nào cũng map ngược được chính xác `page_start` và `page_end`.

### Bước 2: Nhận diện khung cấu trúc pháp lý (`_HEADING` + lọc `_TOC_TAIL`)
Regex `_HEADING` quét các mốc đầu dòng thực sự của hợp đồng Việt Nam:
* `PHỤ LỤC` (chỉ bắt chữ in hoa, ví dụ `PHỤ LỤC 1 – ĐẶC ĐIỂM`, tránh nhận nhầm câu văn xuôi *"theo quy định tại phụ lục kèm theo"*).
* `Phần ...`, `Chương ...`, `Điều <số>` **bắt buộc theo sau bởi `.`, `:`, `–`, `-` hoặc xuống dòng** (nên câu *"Điều 5 của Hợp đồng này quy định..."* nằm ở đầu dòng sẽ không bị hiểu nhầm là tiêu đề Điều mới!).
* **Lọc Mục lục (`_TOC_TAIL`):** Nếu dòng khớp mẫu `ĐIỀU 2. MỤC ĐÍCH.....10` (có dãy chấm dẫn + số trang cuối dòng), hệ thống loại bỏ để mục lục không cắt vụn cấu trúc văn bản thật.

Mỗi chunk sinh ra đều mang thuộc tính **`section_path`** đầy đủ, ví dụ:
`Hợp đồng/ĐIỀU 9. BẢO HÀNH NHÀ Ở/Khoản 5` (sau này C06 Retrieval sẽ dùng `path_context()` để đưa tên Điều vào ngữ cảnh tìm kiếm cho các khoản ngắn).

### Bước 3: Chia nhỏ theo khoản và câu tôn trọng ngữ nghĩa (`_SUB_BREAK`, `_SENTENCE_END`)
Nếu một Điều vượt quá `max_chars` (mặc định `1800` ký tự):
* Ưu tiên cắt tại các ranh giới khoản/điểm đầu dòng (`1.`, `2)`, `a)`, hoặc dòng trống) bằng `_SUB_BREAK`.
* Nếu một khoản vẫn quá dài, dùng `_SENTENCE_END`, nhưng **bảo vệ không cắt nhầm** tại số thập phân (`12.5`), số hiệu văn bản (`06/2019/TT-BXD`), từ viết tắt (`TP.`, `Q.`, `v.v.`) hoặc các từ nối điều kiện (`_CONTINUATION`: *"trừ trường hợp"*, *"ngoại trừ"*, *"tuy nhiên"*).

### Bước 4: Bất biến `noi_dung` nguyên văn & ID tất định (`extraction_version`)
* `noi_dung` của `ChunkRecord` luôn là **lát cắt chuỗi gốc nguyên văn (`raw_text[global_start:global_end]`)**, tuyệt đối không `.strip()` hay gộp khoảng trắng. Nhờ vậy, quote từ LLM hay từ regex luôn đối chiếu ngược chính xác 100% vị trí trong tài liệu.
* `extraction_version(source_sha256, parser_version, max_chars)` băm SHA-256 các thông số thành phần. Nếu giữ nguyên PDF và chunker version, chạy lại cho đúng cùng danh sách `doan_id`; đổi PDF hoặc nâng cấp chunker sẽ tự sinh version mới để writer DB không ghi đè hoặc lẫn lộn dữ liệu cũ.

---

## 4. Trích xuất `ContractProfile` & `Facts` (`C02`): Rule vs Local LLM (`SemanticDocumentExtractor`)

`C02` tạo ra `ContractProfile` gồm 4 nhóm dữ liệu:
1. `profile` (`ProfileFields`): loại hợp đồng, loại/tình trạng tài sản, chế độ giao dịch, cờ `la_nha_xay_moi`, `la_nha_o_xa_hoi`, `co_thoa_thuan_trong_tai`, giá bán, diện tích, tỷ lệ thanh toán, bảo hành...
2. `subjects` (`ProfileSubject`): danh sách chủ thể theo vai trò (`BEN_BAN`, `BEN_MUA`, tư cách chủ đầu tư, đăng ký kinh doanh, tài khoản ngân hàng).
3. `time_markers` (`ProfileTimeMarker`): ngày giao kết (`SIGNING`), ngày sử dụng mẫu (`TEMPLATE_USE`), mốc đặt cọc (`DEPOSIT_AGREEMENT`)...
4. `facts` & `evidence` (`ExtractedFact`, `ProfileEvidence`): mỗi fact lưu `ten_truong`, `gia_tri_chuan_json`, `trang_thai`, `evidence_ids`, và từng `ProfileEvidence` lưu quote + chunk + offsets.

### Kiến trúc 2 lớp giữa Rule Extractor và Local LLM (`Qwen`/Ollama)

Tại sao không bỏ hẳn rule (`profile_extractor.py`) để giao hết cho LLM, hoặc ngược lại?

* **Lớp 1 — `extract_profile()` (Rule-based, luôn chạy được offline):** Bắt các cấu trúc lặp chuẩn mực (ngày ký hợp đồng dạng *"ngày ... tháng ... năm ..."*, số tiền, tỷ lệ phần trăm, mã hợp đồng, tiêu đề bảng chủ thể) với tốc độ mili-giây, chi phí 0đ, và độ tái lập 100%.
* **Lớp 2 — `SemanticDocumentExtractor` (`semantic_extractor.py` + `OllamaDocumentClient`, tùy chọn):** Gọi model local (ví dụ Qwen qua Ollama với timeout & JSON schema chặt) cho **9 trường dễ sai/biến thiên văn phong**:
  `warranty_months`, `dien_tich` (thông thủy), `gross_area_m2` (sàn xây dựng), `land_area_m2` (thửa đất), `ten_ben_ban`, `ten_ben_mua`, `dia_chi_ben_ban`, `dia_chi_ben_mua`, `phuong_thuc_thanh_toan`.

**Cơ chế kiểm soát chống ảo giác của `SemanticDocumentExtractor`:**
1. **Prompt tách vai trò dữ liệu:** Nhắc rõ hợp đồng thường trộn 3 loại diện tích (`diện tích sử dụng căn hộ` vs `sàn xây dựng` vs `thửa đất`) và cấm tự đổi năm sang tháng.
2. **Kiểm tra quote nguyên văn (`quote` substring check):** Mọi `FactProposal` trả về bắt buộc phải trích một đoạn `quote` khớp nguyên văn trong chính chunk đầu vào (`source_id`). Nếu LLM tự sửa chữ hoặc bịa quote, đề xuất bị loại bỏ ngay.
3. **Nguyên tắc vàng: *"Exact quotes prove attribution, not semantic truth"*:** Ngay cả khi `quote` khớp nguyên văn 100% trong PDF, hệ thống vẫn không tin mù quáng rằng LLM chọn đúng vai trò ngữ nghĩa (ví dụ LLM có thể quote đúng một dòng nhưng dòng đó là *địa chỉ dự án* thay vì *trụ sở Bên Bán*). Vì vậy, mọi fact do LLM đề xuất đều mang trạng thái **`DERIVED_REVIEW_PENDING`** (`phuong_phap=LOCAL_LLM_EXACT_QUOTE_V1@<model_digest>`) khi merge vào `ContractProfile` — và do `SourceFactVerifier` ở C07 hiện chỉ nhận facts `EXTRACTED`, đề xuất này không tự nâng thành số liệu verified.

**Vận hành, ngân sách & kiểm soát tài nguyên chế độ Hybrid (`documents_local_llm.md`):**
* **Kích hoạt tách biệt:** Bật bằng `DOCUMENTS_EXTRACTOR=hybrid` (mặc định `.env.example` vẫn là `rules`), hoàn toàn độc lập với `ASSESSMENT_LLM` của tầng C07. Model chạy trên host qua `OllamaDocumentClient` (`qwen3.5:9b-q4_K_M`, temperature `0`, context `4.096`, max output `512`), không có fallback cloud.
* **Ngân sách cửa sổ & Cache:** Mặc định chỉ xét tối đa `DOCUMENTS_LLM_MAX_CALLS=2` cửa sổ (tối đa `1.400` ký tự/cửa sổ) cho các trường mà rule chưa tìm ra. Phản hồi được cache cục bộ tại `SOURCE_CACHE_DIR/documents_llm/` theo khóa `(input, source, model_digest, options, prompt/schema)` — cache hit không ghi lượt gọi giả.
* **Audit X02 & Diagnostics:** Mọi lượt `/api/chat` thực tế ghi X02 với `provider="OLLAMA_LOCAL"`, `module="DOCUMENT_INTELLIGENCE"`; bảng diagnostics phân biệt rõ `DOCUMENT_LLM_CALLED`, `DOCUMENT_LLM_CACHE_HIT`, `DOCUMENT_LLM_BUDGET_LIMIT`, `DOCUMENT_LLM_NO_CANDIDATE_WINDOWS` và lỗi model/timeout (lỗi hoặc timeout sẽ fallback sạch về output `rules`, không ngầm đọc reference QA).

---

## 5. Trích xuất `Citations` (`C03`): Tại sao tách `citation_extractor` khỏi `C09`?

Trong `modules/documents/`, `extract_citations()` cùng [`find_citation_spans()`](../../backend/src/legal_checker/modules/documents/citation_spans.py) làm một việc duy nhất: **phát hiện mọi lần hợp đồng nhắc tới văn bản pháp luật** (ví dụ *"Luật Nhà ở số 65/2014/QH13"*, *"Nghị định 99/2015/NĐ-CP"*, *"Thông tư số 06/2019/TT-BXD"* — kể cả khi tên/số văn bản bị ngắt dòng vắt qua ranh giới chunk hoặc xuống dòng trước `CP`), chuẩn hóa thô `CitationNormalization`, ghi `CitationPosition` (chunk, trang, start/end), và dừng ở trạng thái `EXTRACTED`.

**Vì sao `C03` không tự tra DB để chấm đúng/sai?**
* Tách biệt trách nhiệm: Nhóm A (Document Intelligence) chỉ đọc PDF và giữ bằng chứng vị trí văn bản, **không phụ thuộc vào tri thức pháp luật (`KnowledgeSnapshot`)**.
* Nhờ vậy, khi cập nhật bộ luật mới (ví dụ bổ sung văn bản mới vào `van_ban_phap_ly`), ta chỉ cần chạy lại `C09 Citation Validation` trên danh sách `C03` đã trích mà không phải parse lại hàng trăm file PDF.

---

## 6. Đọc tiếp & Tham chiếu nhanh

* **Bước kế tiếp trong bộ Deep Dive:** [04 — Scope & Temporal Resolution](04-scope-and-temporal-resolution.md)
* **Đối chiếu code:**
  * [`PdfDocumentIntelligence`](../../backend/src/legal_checker/modules/documents/service.py) — điều phối `storage.read → reader.extract → check SHA → chunk_document → extract_profile → SemanticDocumentExtractor.merge → extract_citations`.
  * [`chunk_document()`](../../backend/src/legal_checker/modules/documents/chunker.py) — giữ lát cắt nguyên văn và `section_path`.
  * [`SemanticDocumentExtractor`](../../backend/src/legal_checker/modules/documents/semantic_extractor.py) — quy tắc kiểm soát quote và gán `DERIVED_REVIEW_PENDING`.
