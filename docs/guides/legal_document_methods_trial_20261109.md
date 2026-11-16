# Thử nghiệm phương pháp xử lý hợp đồng pháp lý — 09/11/2026

## 1. Phạm vi và mục tiêu

Bản này thay cách vá theo một PDF bằng phương pháp xử lý text nguồn, cấu trúc
và evidence có thể kiểm tra trên nhiều hợp đồng. Mục tiêu là bảo toàn nguồn và
đưa đúng ngữ cảnh cho tiêu chí; không đặt mục tiêu mọi kết quả phải SATISFIED.

Policy máy đọc: [DOCUMENT_SOURCE_CONTEXT_V2](../contracts/document_chunking_policy.json).
Các DTO C01–C13, enum, schema SQL và API không thay đổi trong thử nghiệm này.

## 2. Nguồn nghiên cứu và quyết định áp dụng

| Nguồn gốc | Phương pháp được mô tả | Áp dụng trong repo |
| --- | --- | --- |
| [Docling: chunking](https://docling-project.github.io/docling/concepts/chunking/) | Chia theo cấu trúc; HybridChunker bổ sung ngân sách tokenizer và ngữ cảnh tiêu đề | Áp dụng nguyên tắc cấu trúc → Khoản/câu → giới hạn dung lượng, bảo toàn lát nguồn; chưa tích hợp Docling hoặc tokenizer của model |
| [MongoDB/LangChain: parent document retrieval](https://www.mongodb.com/docs/atlas/ai-integrations/langchain/parent-document-retrieval/) | Tìm child nhỏ rồi cấp thêm parent cho model | Mở một phần ngữ cảnh cha/liền kề và dẫn chiếu nội bộ có giới hạn; dùng PostgreSQL hiện có, không thêm MongoDB/LangChain |
| [LexNLP: citation extraction](https://lexpredict-lexnlp.readthedocs.io/en/latest/modules/extract/en/citations.html) | Trích viện dẫn từ text bằng quy tắc theo định dạng/jurisdiction | Áp dụng cách tách finder source spans khỏi các chunk tìm kiếm; dùng matcher tiếng Việt hiện có, không dùng bộ định dạng án lệ Mỹ để nhận luật Việt Nam |
| [ContractNLI](https://stanfordnlp.github.io/contract-nli/) | Đánh giá mệnh đề theo hợp đồng và các evidence spans; phân biệt hỗ trợ, mâu thuẫn, không đề cập | Tiếp tục đánh giá criterion từ knowledge bằng nguồn cụ thể; bỏ recipe GTC tự kết luận từ ba mẫu câu. Không đổi trực tiếp ba nhãn NLI thành bốn enum C07 |
| [LegalBench-RAG](https://arxiv.org/abs/2408.10343) | Đánh giá Retrieval bằng đoạn nguồn liên quan chính xác | Đo vị trí/span và khả năng đưa đủ các đoạn liên quan; không dùng số lượng SATISFIED làm metric Retrieval |

Đây là các phương pháp trong tài liệu kỹ thuật/nghiên cứu gốc, không phải bằng
chứng rằng mọi sản phẩm legal AI đều có cùng kiến trúc. Kết quả tiếng Anh hoặc
benchmark khác jurisdiction không chứng minh chất lượng cho hợp đồng Việt Nam.

## 3. Nhóm A — chunk và viện dẫn

`documents/chunker.py` chuyển từ structural-v1 sang structural-sentences-v2:

1. Giữ Phụ lục/Phần/Chương/Điều làm đơn vị cha, bỏ dòng mục lục đã nhận diện.
2. Khi dài, xét Khoản/Điểm, đoạn và câu; nhận thêm số khoản dạng 2.1/2.1.1.
3. Tránh cắt số thập phân, số tiền, từ viết tắt và ngay trước một số cách mở ngoại lệ.
4. Finder nhận diện viện dẫn trên source text trước để bảo vệ cụm viện dẫn khỏi
   việc cắt tại giới hạn kích thước.
5. Giữ nguyên từng ký tự trong lát nguồn. Không lặp tiêu đề/chèn text tổng hợp vào
   `noi_dung`; ngữ cảnh mở rộng vẫn trỏ tới các chunk nguồn riêng.

1.800 ký tự là mục tiêu mềm. Nếu một câu cần thêm dung lượng, cho phép tới hai lần
mục tiêu trước khi dùng fallback. Trường hợp nguồn không có dấu câu vẫn cần cắt
có giới hạn; `split_reason` trong metadata extraction/workbook thử ghi rõ hạn chế.
Không gọi đây là ngân sách token của embedding/LLM. Chưa giải quyết việc đọc bảng
theo layout, OCR hoặc thứ tự đọc nhiều cột; đó là các phép thử adapter riêng.

`documents/citation_spans.py` chỉ xác định viện dẫn quan sát được. `citation_extractor.py`
source-spans-v5 tìm trên vùng text nguồn liên tục đọc được rồi ánh xạ span vào
các chunk thật. Không còn phụ thuộc cửa sổ 256 ký tự của hai chunk liền nhau.
Một viện dẫn đi qua ba hoặc nhiều chunk vẫn giữ được các phần quote/offset.
Trang không đọc được là rào chắn; không ghép hai mảnh chữ qua trang đó.
Finder cũng không coi cụm chung “Luật Áp Dụng”/“Luật Việt Nam” là tên một văn bản.
Một số banner in hoa lặp lại được dùng làm rào chắn khi đọc tên luật, không bị xóa
khỏi nguồn. Nếu chỉ còn “Điều 57 Luật” trước banner, giữ tham chiếu AMBIGUOUS,
không biến chữ của banner thành tên luật. Đây vẫn là heuristic text, chưa thay
layout parser hoặc bộ từ điển pháp luật tiếng Việt đầy đủ.

## 4. Nhóm B — lấy thêm ngữ cảnh có kiểm soát

Sau khi tìm/chọn ứng viên bằng BM25 hoặc hybrid/reranker đang có:

- Lấy thêm đoạn mở đầu hoặc lân cận thuộc cùng Điều và cùng nhánh Phụ lục.
- Có thể theo dẫn chiếu nội bộ tường minh như “Điều 8 của Hợp đồng này”. Chỉ mở
  khi đích cấu trúc là duy nhất; viện dẫn Điều của một luật không được coi là
  Điều của hợp đồng. Dẫn chiếu mơ hồ giữ chưa phân giải.
- Tối đa ba chunk thêm, tối đa 6.000 ký tự thêm; tổng số rows vẫn chịu `top_k`.
- C06 ghi `scores.parent_context` / `scores.internal_reference_context` và vị trí
  anchor. Các điểm này mô tả vai trò ngữ cảnh, không giả làm điểm BM25 hay độ đúng.
- Context chỉ từ IDs của extraction đang chạy. Hai Điều cùng số nhưng khác phụ
  lục không được gộp. Không dùng chunk seed cũ để bù cho source mới.

Đây là ngữ cảnh bổ sung có giới hạn, không trả toàn bộ một Điều dài vô hạn và
không tự chứng minh nội dung liên quan đáp ứng criterion.

## 5. Nhóm C — bỏ kết luận GTC phụ thuộc mẫu câu

Đã bỏ `general_terms_content.py` và nhánh admission riêng cho HYC015_02. Ba câu
trong PDF có thể là evidence cần xét, nhưng không tự tạo một Observation SATISFIED.

Luồng hiện tại:

```text
C05 + criterion/rules của knowledge pin
                 ↓
C06: đoạn tìm thấy + ngữ cảnh có ghi vai trò
                 ↓
LLM đề xuất kết luận và các quote hỗ trợ mệnh đề
                 ↓
Backend kiểm quote/offset, ownership, scope/version, facts và ngoại lệ
                 ↓
C07: kết quả bản nháp hoặc UNKNOWN kèm lý do
```

Prompt C07_SEMANTIC_V13 cung cấp vai trò của các rows C06 và yêu cầu kiểm quan hệ
giữa các đoạn, chủ thể, điều kiện/ngoại lệ. Không đồng nhất một từ khóa, nhan đề
nội quy hoặc việc xuất hiện trong Retrieval với một kết luận pháp lý.

Các phép tính Decimal và predicate nội dung có định nghĩa rõ khác vẫn giữ nguyên.
Không bỏ các gate C07, không đổi human_verified hoặc tự xác nhận sự kiện đã xảy ra.

Kiểm tra provider thật phát hiện model dùng quote ID `Q17` cả ở trích dẫn và
`candidate_facts.evidence_ids`, nhưng validator trước chỉ nhận chunk/external IDs ở
vị trí sau. Adapter hiện chấp nhận quote ID có trong catalog của chính input đó;
ID ngoài catalog vẫn bị loại. Việc tham chiếu được nguồn không xác minh giá trị
fact; các candidate facts vẫn không cấp numeric/applicability verification.

## 6. Dataset, PDF và workbook

PDF mới nhất đang kiểm tra là PDF360_DRAFT_NORMALIZED_V3_20261108. Việc chia text
không yêu cầu sửa nội dung PDF; mọi checksum phải giữ nguyên. Chưa phát hiện lỗi
nguồn thì không bổ sung điều khoản/ngày/số hiệu để làm cho một nhãn đẹp hơn.

Workbook seed TEAM và các report cũ vẫn pin source/chunk/version cũ. Chúng là
baseline tham chiếu riêng, không tự đổi thành output đã xác nhận của chunker mới.
Không thay doan_id trong C06/C07 cũ hoặc ghi hash mới lên đáp án cũ.

Công cụ thử xuất `DOCUMENT_METHODS_TRIAL.xlsx` gồm metric từng PDF, các chunks mới,
và vị trí viện dẫn. Đây là **workbook xem/đối chiếu, không phải workbook seed**:
không có đáp án C07–C13 mới, không đổi các nhãn pháp lý tham chiếu.

Khi phát hành lại toàn dataset để seed, phải dựng C02/C03, index/C06 và các payload
phụ thuộc từ cùng version; kiểm chứng lại expected outputs và phát hành cùng manifest.
Không thể chỉ đổi bảng doan_hop_dong mà giữ nguyên mọi đáp án/offset phía sau.

## 7. Chạy kiểm tra lặp lại

```bash
source .venv/bin/activate
python -m devtools.document_methods_eval \
  --pdf-root /duong/dan/bo_pdf_v3 \
  --splits /duong/dan/splits.csv \
  --out data/private/document_methods_dev \
  --workers 4
```

CSV splits có `hop_dong_id,split`; lấy đúng split đã chốt theo họ hợp đồng gốc.
Mặc định chỉ DEV. Sau khi chốt method, thêm `--split VALIDATION` để kiểm độc lập.
Công cụ không nhận TEST và không dùng nhãn đáp án pháp lý để điều chỉnh method.
Hai tham số `--baseline-chunker` / `--baseline-citations` có thể trỏ tới file code
bản trước để so sánh; không giữ thêm một engine legacy trong production.

Kiểm thử nguồn/span không thay thế đánh giá Recall@K, precision và chất lượng
kết luận theo các evidence do người đánh giá xác nhận. LLM lỗi quota vẫn phải
hiện trạng thái lỗi/chưa xử lý, không chuyển thành thiếu nội dung hợp đồng.

## 8. Kết quả thực nghiệm

### 8.1 PDF DEV/VALIDATION theo split hiện hành

Đã chạy trên PDF v3 thật, kiểm checksum theo manifest, cố định phương pháp sau DEV
rồi kiểm VALIDATION; không nạp 60 PDF TEST và không dùng các nhãn đáp án pháp lý.

| Chỉ số | DEV | VALIDATION | Tổng |
| --- | ---: | ---: | ---: |
| PDF đã kiểm | 240 | 60 | 300 |
| Chunk theo phương pháp trước | 24.566 | 5.287 | 29.853 |
| Chunk theo phương pháp mới | 23.615 | 5.020 | 28.635 |
| Ranh giới cắt giữa observed citation span — trước | 64 | 16 | 80 |
| Ranh giới cắt giữa observed citation span — sau | 0 | 0 | 0 |
| PDF có thay đổi normalized facts | 16 | 0 | 16 |
| PDF có thay đổi tập citation keys so với bản trước | 40 | 8 | 48 |
| Lỗi bảo toàn nội dung/quote-offset | 0 | 0 | 0 |

Các metric dùng cùng finder nguồn để so sánh hai cách chia. 80 → 0 là kết quả
về ranh giới của các viện dẫn đã nhận diện, **không phải** citation recall 100%.
Phép bảo toàn nội dung đối chiếu phần text không phải whitespace; từng quote/offset
vẫn khớp nguyên văn chunk nguồn. Không đoán chất lượng pháp lý từ số chunk ít hơn.

16 thay đổi facts đều nằm ở tên bên bán: có trường hợp tên được đọc đầy đủ hơn,
có trường hợp trước không lấy được. Chúng được giữ trong workbook để review, chưa
tự nâng thành human_verified. 48 tập citation keys thay đổi gồm các tên bị cắt cụt,
tên+năm được đọc đầy đủ và các cụm chung bị loại. Không coi mọi key biến mất là
một viện dẫn pháp lý bị mất hoặc mọi key mới là một viện dẫn đã xác thực.

### 8.2 Kiểm tra lại hợp đồng demo

PDF SHA-256 vẫn là
`9bac4ac8ae4a2e71584c8b421bce6106b3a3cec54061bfc678e869f2430b8e97`.
Knowledge pin vẫn là
`32d59bcb9efe506389543bae5ee819d2d07d4a322425fa2d3ffa377c1eff698b`.

| Phần | Kết quả |
| --- | --- |
| Text source | 78 trang; PDF không đổi |
| Chunks | 139 của implementation trước → 131; extraction version mới `04025599616d` |
| C02 | Giữ 56 facts |
| C05 | Giữ 75 CONFIRMED và 248 NOT_APPLICABLE |
| C06 HYC015_02 | Có cả đoạn liệt kê nội quy, đoạn gắn với hợp đồng và đoạn xác định mốc hiệu lực |
| C09 | Giữ 10 VALID và 1 UNKNOWN; không điền số hiệu/năm giả |
| Native GTC rule | Đã bỏ; không tự tạo Observation SATISFIED |

Đã kiểm một criterion với provider thật, có lưu audit local:

1. Lượt đầu: TEMPORARY_HTTP_ERROR; giữ lỗi/chưa kết luận.
2. Lượt sau: model đề xuất SATISFIED nhưng adapter từ chối candidate fact tham
   chiếu `Q17`; phát hiện và sửa quy ước quote ID như mục 5.
3. Sau sửa: `gemini-3.5-flash-lite`, prompt C07_SEMANTIC_V13, đề xuất được backend
   kiểm thành C07 SATISFIED, một quote nguồn, review_status=PENDING.

Không chọn lọc/xóa hai phản hồi thất bại khỏi audit. Đây là **kiểm tra riêng một
criterion bằng provider thật**, không phải chạy lại toàn pipeline hoặc xác nhận
mọi requirement của hợp đồng tuân thủ. Không tạo/sửa báo cáo UI từ phép kiểm này.

### 8.3 Kiểm thử, artifact và nghiệm thu

- Backend: **1.640 passed, 7 skipped**; một cảnh báo deprecation của Starlette.
- Ruff lint/format theo `backend/pyproject.toml`: pass.
- Có kiểm tra chống mất nguồn, cite qua nhiều chunk, trang không đọc được, cite
  giả qua banner, phạm vi parent/annex, dẫn chiếu mơ hồ và giới hạn context.
- Có regression test: ba câu của PDF demo không tự tạo kết luận GTC; quote ID hợp
  lệ trong candidate fact được chấp nhận nhưng fact vẫn unverified, ID lạ bị loại.
- **21 report đang lưu giữ nguyên JSON/hash** trong kiểm tra DB; không seed lại.

Thư mục artifact xem được:

```text
/home/chienqt/Downloads/legal_document_methods_trial_20261109/
```

`DOCUMENT_METHODS_TRIAL_DEV_VALIDATION.xlsx` khoảng 16 MB là workbook đối chiếu
300 PDF. Có các file DEV/VALIDATION riêng, EVAL_SUMMARY.json và lịch sử kiểm provider.
Các ký tự điều khiển không hợp lệ với XML được escape thành `\\uXXXX` trong ô xem;
JSON/source vẫn giữ text thật và offsets. File này không có đủ schema/QA để seed.

Bằng chứng kỹ thuật đầy đủ nằm ngoài Git tại
`data/private/legal_methods_trial_20261109/`: `dev_frozen/`, `validation/`,
`preflight.json`, `one_criterion_result*.json`, `one_criterion_audit.jsonl`,
`backend_tests.log` và `history_preserved.json`. Kiểm tra container dùng lại
phản hồi provider đã lưu chỉ được tính là **replay cùng input digest**, không tính
thành một lượt inference/provider hoặc một báo cáo mới.

### 8.4 Giới hạn còn lại

Chưa có metric semantic/Recall@K do người đánh giá xác nhận trên toàn corpus cho
method mới; không tuyên bố baseline pháp lý đã đạt. Chưa thay parser PDF bằng
Docling, chưa có layout table reconstruction/OCR và ngân sách tokenizer theo model.
Giữ các mục này thành nghiệm thu riêng; không chỉnh PDF hoặc đáp án workbook để
che lỗi parser/LLM. Báo cáo cũ vẫn giữ kết quả của implementation đã tạo ra nó.

### 8.5 Trách nhiệm khi năm người tiếp tục phát triển

| Người | Phần dùng chung đã thay đổi | Điều phải giữ khi tiếp tục |
| --- | --- | --- |
| 1 — dataset/platform | Policy và workbook đối chiếu DEV/VALIDATION | Không đổi seed manifest/hash hoặc gold cũ thành version mới nếu chưa dựng và kiểm toàn chuỗi phụ thuộc |
| 2 — Documents | Chunker, source citation finder và ánh xạ vị trí | Giữ source hash/offset, thử thêm bảng/layout/OCR độc lập, không sửa PDF để bù lỗi extractor |
| 3 — Scope/Retrieval/Citation | C06 có ngữ cảnh cấu trúc và dẫn chiếu có giới hạn | Chỉ dùng active chunk IDs; score context không phải bằng chứng tuân thủ; ambiguity giữ chưa xác định |
| 4 — Reasoning/Risk/Recommendation | Bỏ auto-SAT GTC, thống nhất quote IDs | Predicate phải từ knowledge pin, facts model vẫn unverified, giữ các C07 gates và nguồn risk |
| 5 — Workflow/FE/Report | Luồng hiện có nhận DTO cũ với extraction/retrieval version mới | Tạo run mới để xem kết quả mới, giữ report cũ và phân biệt kiểm module/replay với full E2E |

### 8.6 Triển khai thử trên k3d

API 2/2, worker 1/1 và scheduler 1/1 đã chạy cùng backend image:

```text
legal-local/backend:image-6d6a99c0d929805798dd1f978527d72e1df0726f8c18fea41e846e23e981bc39
```

Worker đọc lại PDF từ storage, đối chiếu toàn bộ chunks/profile với input đã dùng
cho lượt provider V13 thành công, rồi replay chính proposal đã lưu. Input digest
khớp; adapter/reasoner trong image mới trả SATISFIED/PENDING với một quote nguồn,
không gọi provider thêm và không sửa report. C09 vẫn 10 VALID, 1 UNKNOWN.
Artifact: `deployed_replay_result.json` trong thư mục bằng chứng.

Frontend trả HTTP 200 tại `http://app.legal-checker.localhost:18880/`. Tại thời điểm
kiểm module/replay chưa tạo report full-pipeline mới; mở report cũ vẫn thấy snapshot cũ. Đây là
image build từ worktree local, chưa commit/push. Argo auto-sync vẫn tạm dừng cho
bản local; không gọi rollout này là một revision đã publish/sync từ Git.

Sau đó đã thực hiện [run E2E mới và rà tám tab/export](e2e_source_context_results_20261109.md).
Đọc biên bản đó để biết kết quả toàn pipeline; không thay bằng chứng E2E bằng các
phép kiểm module/replay trong tài liệu này.
