# Sửa viện dẫn và evidence điều kiện giao dịch chung — 09/11/2026

> **Lịch sử bản sửa trước.** Thử nghiệm tiếp theo đã thay regex-v4 bằng source-spans-v5,
> thay chunker và bỏ recipe GTC tự đề xuất SATISFIED. Xem
> [phương pháp và trạng thái hiện hành](legal_document_methods_trial_20261109.md).
> Kết quả native GTC bên dưới chỉ là bằng chứng của implementation trước, không
> dùng để mô tả kết luận của code mới.

## 1. Phát hiện trên PDF baseline v3

Run lịch sử `REPORT_0fe8bebb-33dd-51fd-a254-d3e11b8b335d` có một C07 UNKNOWN
(HYC015_02) và bảy C09 UNKNOWN. Rà lại nguồn thấy:

- Chunker cắt giữa “Luật Kinh doanh” và “Bất động sản số 66/2014/QH13”. Extractor
  từng chunk độc lập tạo một tên luật cụt và một citation số hiệu riêng.
- C09 chỉ chấp nhận số hiệu nên cả tên kèm năm rõ ràng như Luật Nhà ở 2014 vẫn UNKNOWN.
- Các dẫn chiếu tĩnh “Luật Nhà ở” chưa được nối với số hiệu rõ ràng của cùng luật
  trong phần căn cứ của chính hợp đồng.
- HYC015_02 chỉ nhận các đoạn không xác định rõ điều kiện chung; chưa nhận Nội quy
  và điều khoản gắn hiệu lực nội quy/phụ lục với hợp đồng ở trang 74/26.

PDF/knowledge không đổi. Không thêm ngày, chữ ký, văn bản luật hoặc xác nhận con người giả.

## 2. Người 2: citation qua ranh giới chunk

`documents/citation_extractor.py`, regex-v4:

- Chỉ ghép khi hai lát nguồn liên tiếp có global_end/global_start và thứ tự khớp.
- Chỉ xét cửa sổ cuối/đầu hữu hạn, xác định span thực sự đi qua ranh giới.
- Một citation ghép giữ tên và số quan sát được trong nguồn, không lấy từ catalog
  để điền ngược vào C03.
- Mỗi mention giữ quote/offset riêng trong chunk gốc; C03 có cả hai vị trí nguồn.
- Loại các mảnh span cũ bị citation ghép bao phủ, tránh một viện dẫn bị tính hai lần.
- Dẫn chiếu động “hiện hành/từng thời điểm” giữ tách khỏi tham chiếu tĩnh.
- Extraction version thay đổi theo regex-v4; snapshot/chunks/facts mới có identity
  riêng. Không sửa IDs/offsets của extraction hoặc report cũ.

Đây là sửa extraction viện dẫn, không phát hành lại bộ chunk workbook hoặc 360 PDF.

## 3. Người 3: C09_CATALOG_IDENTITY_V2

Policy máy đọc: [citation_identity_policy.json](../contracts/citation_identity_policy.json).

Thứ tự xác định identity:

1. Số hiệu rõ ràng khớp duy nhất catalog; tên/năm mâu thuẫn phải được ghi nhận.
2. Tên canonical + **năm quan sát được** khớp duy nhất văn bản catalog. Năm dùng là
   năm của số hiệu/ban hành, không phải năm có hiệu lực.
3. Tên không năm/số, tham chiếu tĩnh, có đúng một phiên bản số hiệu tường minh
   cùng tên trong chính hợp đồng. Anchor phải EXTRACTED và có identity catalog đã
   xác minh. Giữ IDs của các citation làm anchor.
4. Không đủ hoặc nhiều ứng viên/anchor xung đột: UNKNOWN. Không chọn luật mới nhất
   hoặc luật có hiệu lực vào ngày ký để đoán ý viện dẫn.

Alias tên chỉ có danh mục tường minh; không dùng fuzzy/subset để chọn identity.
Một catalog không đầy đủ chỉ có một văn bản cũng không đủ để định danh tên trần.
Dẫn chiếu động không bị neo vào số hiệu tĩnh của phần căn cứ.

Sau identity, temporal và domain được kiểm riêng. Ví dụ tên+năm 2014 ở giao dịch
2025 vẫn có thể STALE; không chuyển sang bản 2023 để tạo VALID. Domain UNKNOWN
vẫn UNKNOWN. Metadata catalog chưa xác minh không được biến thành verified finding.

C03 raw/normalized/extraction status giữ nguyên dữ kiện nguồn. C09 lưu số hiệu
**được phân giải** qua normalized_van_ban_id, không bịa observed_number trong C03.
Provenance ghi identity_policy_id, catalog_identity_matched, catalog_number_matched
đúng thực tế và checks.identity.anchor_citation_ids. Tên+năm/anchor không được ghi
nhầm là đã quan sát số hiệu trực tiếp.

Policy này thay giới hạn “chỉ số hiệu” của phiên bản trước. QA/seed/report lịch sử
không được đổi nhãn ngược; đánh giá C09 mới phải ghi rõ policy đang dùng.

## 4. Người 3–4: HYC015_02 và nội quy đính kèm

Retrieval có anchor cho văn bản nội quy có điều khoản hiệu lực, sự dẫn nhập vào
hợp đồng và điều khoản hiệu lực phụ lục. PDF hiện có:

- Trang 74: nội quy có hiệu lực kể từ ngày chủ đầu tư ký ban hành; nội quy là một
  phần không thể tách rời của hợp đồng và ràng buộc người mua/nhận chuyển nhượng.
- Trang 26: hiệu lực hợp đồng và phụ lục đính kèm.

Đó là **candidates**, không tự là kết luận pháp lý. Semantic V11 nhận thêm Điều 3
Luật BVQLNTD 2010 và Điều 406 BLDS 2015 đúng khoảng hiệu lực để kiểm định nghĩa.
Không đòi tài liệu phải mang nhãn “điều kiện giao dịch chung”; cũng không tự coi
mọi nội quy/hợp đồng dịch vụ riêng là điều kiện bán hàng.

Trong DRAFT_REVIEW, nếu xác định được đúng văn bản và cách xác định sự kiện bắt đầu
áp dụng thì kiểm nội dung đó. Không bắt dự thảo chứng minh sự kiện ban hành đã xảy
ra, không lấy C01 TEMPLATE_USE thành ngày hiệu lực nội quy. Công khai/niêm yết thực
tế là tiêu chí khác và không được xác nhận chỉ bằng một điều khoản dự thảo.

Nguồn định nghĩa và nghĩa vụ: [Điều 3, 18 Luật BVQLNTD 2010](https://chinhphu.vn/default.aspx?docid=98755&pageid=27160),
[BLDS 2015, Điều 406](https://datafiles.chinhphu.vn/cpp/files/vbpq/2016/01/91_.pdf).
Đây là chế độ pháp luật của kịch bản 2017, không mặc định áp cùng phiên bản cho giao dịch khác.

## 4.1 Kiểm tra nội dung GTC bằng backend có phạm vi hẹp

Việc chỉ thêm evidence/nhắc prompt chưa đủ ổn định: cùng nguồn có run LLM nhận,
có run vẫn đòi văn bản độc lập. `general_terms_content.py` bổ sung recipe
`DRAFT_INCORPORATED_RESIDENTIAL_RULES_V1`, chỉ cho PV_HYC015/ART_VBPL008_18 trong
dự thảo mua bán căn hộ tiêu dùng. Recipe kiểm ba quote:

1. Hợp đồng liệt kê một bản nội quy quản lý sử dụng nhà chung cư kèm theo.
2. Chính nội quy tuyên bố là phần không thể tách rời của hợp đồng mua bán căn hộ.
3. Nội quy ghi rõ mốc có hiệu lực là ngày chủ đầu tư ký ban hành.

Sự kiện xác định mốc khác bằng chứng sự kiện đã xảy ra. Recipe chỉ kiểm nội dung
bộ quy tắc đã dẫn nhập trong dự thảo, không xác nhận ký ban hành/công khai/niêm yết.
Đây là binding đích đánh giá có giới hạn; không áp cho mọi nội quy hay hợp đồng
khác. Thiếu một liên kết, có mốc khác/mâu thuẫn, nguồn không đọc đủ, không khai báo
đủ bộ tài liệu, C06 chưa chọn hoặc mode FULL thì không tự kết luận.

Các quote đi qua C06 → automatic backend review → C07 reasoner bình thường.
Scope/version/source/ngoại lệ/context/hash vẫn được kiểm; không đổi human_verified.
C07 ghi model_version bằng recipe backend và NO_LLM_EXACT_CONTENT_V1, giữ PENDING.
Không tính đây là lượt LLM đã chạy hoặc đã được con người duyệt.

## 4.2 Nhánh mặc định giao tài sản phát hiện khi chạy hồi quy

Run đầu của bản sửa làm rõ thêm hai vấn đề: DS436_01 chỉ nhận Điều 16 Thông báo,
chưa nhận Điều 8 Giao nhận căn hộ; DS435_02 có nhánh không-thỏa-thuận đã được xác
nhận nhưng model vẫn đòi phải có thỏa thuận địa điểm.

Retrieval bổ sung anchor địa điểm/phương thức giao tới điều khoản giao nhận,
không nhầm lịch thanh toán nhiều đợt với giao tài sản nhiều đợt. Semantic V11
làm rõ cơ chế mặc định của Điều 277/435/436: thiếu thỏa thuận được luật bổ sung
không tự là vi phạm/UNKNOWN; giao nhiều đợt là phương án tùy thỏa thuận. Không
xác nhận đã bàn giao hoặc tự chép thêm thỏa thuận vào PDF.

## 4.3 Phục hồi batch rà toàn văn

Một run kiểm chứng gặp DOCUMENT_REVIEW_INVALID_MATRIX: sau hai phản hồi không
đúng ma trận, reviewer dừng cả artifact. Đây là lỗi xử lý provider, không phải
hợp đồng thiếu thông tin. Full-document prompt V5 bổ sung:

- Lượt repair nhận chính lỗi validation cùng manifest đúng của batch.
- Nếu batch vẫn lỗi, chia đôi nhóm criterion và chạy lại từng nhóm với đủ source.
- Bỏ toàn bộ phản hồi parent thất bại; chỉ ghép children đã validate chính xác
  toàn bộ chunk aliases và criterion aliases. Không tự điền ô ma trận.
- Số lần gọi/chi phí criterion, gồm các lượt thất bại và repair, vẫn nằm trong
  ngân sách chung. Batch một criterion vẫn lỗi hoặc hết ngân sách thì fail closed;
  không tạo artifact chứng minh coverage một phần như coverage đầy đủ.

Có test provider cố tình bỏ criterion ở batch lớn, chỉ trả đúng khi chia nhỏ;
kiểm tra artifact cuối đủ ma trận. Test hết ngân sách xác nhận không lưu thêm
artifact/proof từ kết quả mới chưa đầy đủ.

## 5. Người 1 và 5: tích hợp, dữ liệu và nghiệm thu

- Không cần seed lại hoặc sửa workbook cho bản sửa code này.
- API/worker/scheduler dùng cùng backend image mới; frontend dùng hợp đồng dữ liệu
  hiện có. Không thêm enum, field C03 bắt buộc hoặc endpoint mới.
- C09 vẫn đủ case/run/contract/hash; C10 giữ riêng nguồn viện dẫn và tuân thủ.
- Kiểm đủ đối tượng, quote, artifact và report; không tính HTTP SUCCESS của LLM
  thành bằng chứng rằng proposal đã qua validation.
- Các báo cáo cũ đóng băng; tạo run mới để thấy kết quả mới.
- C12 human review và publish vẫn riêng; COMPLETED không phải human approval.

## 6. Kết quả kiểm tra

### 6.1 Kiểm tra trực tiếp trong worker sau bản sửa cuối

Backend, worker và scheduler đã rollout cùng image local:

```text
legal-local/backend:image-2648f74ededa682ecc275ac7b5b9d10ea5fdcf4e8f0cac9b02f38fab4b63f3e5
```

Kiểm tra trong container worker đọc lại PDF đã upload, đối chiếu chunks/profile
với snapshot của ca `CA_UP_C0DA48500613`, sau đó dùng C05/C06 của chính run
`RUN_3c409a2be35347df92e7a422d52edfee` để chạy lại phần kiểm tra có liên quan.

| Kiểm tra | Kết quả |
| --- | --- |
| PDF | Baseline v3, 78 trang; SHA-256 `9bac4ac8ae4a2e71584c8b421bce6106b3a3cec54061bfc678e869f2430b8e97` |
| Knowledge | `V750_RUNTIME_ALIGNMENT_20261108`; SHA-256 `32d59bcb9efe506389543bae5ee819d2d07d4a322425fa2d3ffa377c1eff698b` |
| C03 | 11 records, giữ đầy đủ các vị trí nguồn |
| C09 | 10 VALID với finding_verified, 1 UNKNOWN |
| C06 của HYC015_02 | Có các đoạn nguồn ở trang 74 và 26 |
| C07 của HYC015_02 | SATISFIED, 3 quotes có offset, review_status=PENDING |
| Nhánh kết luận | `DRAFT_INCORPORATED_RESIDENTIAL_RULES_V1` / `NO_LLM_EXACT_CONTENT_V1` |
| Gọi provider trong phép kiểm tra này | 0 |
| Ghi lại report/run | Không |

Đây là **kiểm tra lại module theo dữ liệu thật, chỉ đọc**, không phải một lần chạy
toàn pipeline mới và không phải thao tác human review. Báo cáo đã lưu trước khi
rollout vẫn giữ kết quả cũ. Muốn UI có báo cáo từ implementation cuối phải tạo run
mới; F5 một report cũ không chạy lại inference.

Số 12 C03 của bản trước bao gồm hai mảnh của cùng một viện dẫn bị cắt ở ranh giới
chunk. Số 11 mới đến từ ghép đúng nguồn, không phải xóa một viện dẫn hợp lệ.

### 6.2 Vì sao còn một viện dẫn UNKNOWN?

Viện dẫn còn lại ghi “Luật bảo vệ người tiêu dùng”, không quan sát được năm hoặc
số hiệu. Catalog có các phiên bản năm 2010 và 2023; trong PDF cũng không có một
viện dẫn số hiệu tường minh của cùng luật để làm anchor theo policy V2.

Có hai cách hợp lệ để xử lý:

1. Người chịu trách nhiệm tài liệu xác nhận và bổ sung số hiệu/năm vào tài liệu
   nguồn, rồi ingest/run lại với checksum nguồn mới.
2. Reviewer ghi quyết định định danh kèm căn cứ và danh tính qua luồng review;
   giữ nguyên raw citation và lịch sử kết quả máy.

Không chọn phiên bản theo ngày ký để suy đoán ý người soạn; không đổi UNKNOWN
thành VALID bằng cấu hình hoặc thêm thông tin nguồn giả. Viện dẫn chưa định danh
khác với viện dẫn đã chứng minh sai.

### 6.3 Kết quả lần chạy toàn pipeline gần nhất và giới hạn

Lần chạy toàn pipeline gần nhất **trước khi thêm recipe GTC cuối** đã hoàn tất:

```text
Case:   CA_UP_C0DA48500613
Run:    RUN_3c409a2be35347df92e7a422d52edfee
Report: REPORT_6303b094-2246-5974-8cf3-82e07c8caa08
```

| Phần | Kết quả đã lưu |
| --- | --- |
| C05 | 75 CONFIRMED, 248 NOT_APPLICABLE; không có scope/version UNKNOWN |
| C07 theo disposition | 74 SATISFIED, 3 MISSING, 7 UNKNOWN cần xử lý, 39 ngoài phạm vi review, 6 không phát sinh điều kiện |
| C08 theo disposition | 52 COMPLIANT, 1 NON_COMPLIANT, 6 INSUFFICIENT, 14 ngoài phạm vi review, 2 không phát sinh điều kiện |
| C09 | 10 VALID, 1 UNKNOWN |
| UI | Đọc được đủ 8 tab; không ghi nhận lỗi JavaScript/HTTP trong kiểm tra trình duyệt |
| Export | JSON và PDF trả HTTP 200; đối chiếu JSON và kiểm tra PDF hợp lệ |
| Lineage | 323 C05 receipts được kiểm; risk cùng run; checksum nguồn khớp; human review vẫn PENDING |

Lần chạy này **chưa phải demo baseline đạt hết nội dung**. Có ba criterion dừng
vì RATE_LIMIT: `TC_PV_DS441_01`, `TC_PV_HYC026_01`, `TC_PV_HYC037_02`. Các kết luận
ngữ nghĩa khác cũng còn chưa ổn định giữa những lần gọi model. HYC015_02 trong
report này vẫn UNKNOWN vì report được tạo trước recipe cuối; phép kiểm tra 6.1
chứng minh nhánh mới xử lý được nó nhưng không sửa ngược report.

Full-document review của run này tạo được artifact hoàn chỉnh, không lặp lại lỗi
INVALID_MATRIX đã thấy ở run trước. Việc chia batch khi ma trận sai đã được kiểm
bằng unit tests; run này không phải bằng chứng rằng nhánh chia batch đã được dùng.

Đầu việc còn lại để nghiệm thu toàn pipeline là xử lý quota/rate limit của provider,
đối chiếu từng kết luận nội dung còn dao động và chạy lại bộ đánh giá. Không được
coi HTTP 200, COMPLETED hoặc bản sửa một criterion là bằng chứng toàn bộ nội dung
hợp đồng đã tuân thủ.

### 6.4 Kiểm thử và dữ liệu lịch sử

- Backend: **1.633 passed, 7 skipped**; có một cảnh báo deprecation của Starlette.
- Ruff lint/format: pass.
- Có tests cho citation qua ranh giới, định danh mâu thuẫn/nhiều ứng viên, GTC thiếu
  liên kết hoặc mốc mâu thuẫn, coverage không đủ và phục hồi batch lỗi trong budget.
- Đối chiếu DB xác nhận **18 report có trước đợt sửa này giữ nguyên JSON/hash**.
  Ba report demo mới được lưu riêng; không ghi đè baseline hoặc báo cáo cũ.
- Không đổi PDF, workbook, seed DB hoặc schema C01–C13 trong bản sửa này.
- Cụm k3d đang chạy. Hai Argo Applications Healthy/OutOfSync, auto-sync tạm dừng
  để kiểm thử image từ worktree local; không gọi trạng thái này là đã đồng bộ Git.
- Code hiện ở nhánh `feat/integration-contract-alignment`, chưa commit/push.

Bằng chứng chi tiết được lưu local trong thư mục bị gitignore
`data/private/citation_gtc_fix_20261109/`:

- `deployed_native_result.json`: kết quả 6.1, source/knowledge hash và C07 có quotes.
- `live_run_verified/summary.json`, `browser_checks.json`, `lineage_checks.json`:
  bằng chứng lần chạy toàn pipeline ở 6.3, gồm cả các lỗi còn tồn tại.
- `backend_tests.log`, `ruff.log`, `ruff_format.log`: kết quả kiểm thử.
- `history_preserved.json`: đối chiếu 18 báo cáo lịch sử.

Không commit các payload/run/export local này vào Git. Tài liệu này ghi kết quả
và giới hạn để người 1–5 dùng cùng một phạm vi nghiệm thu.
