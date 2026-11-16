# Hoàn thiện điều kiện phát sinh, numeric và mốc áp dụng — 09/11/2026

## 1. Bản sửa này giải quyết việc gì?

Run lịch sử `REPORT_d709c2bf-64d3-529c-8a99-84469324d4e0` có 17 yêu cầu thiếu căn cứ:
9 yêu cầu ở phần nội dung và 8 yêu cầu ở phạm vi/thời gian. Các con số đó không
phải kết quả của bản sửa hiện tại. Không ghi đè hoặc đổi nhãn báo cáo lịch sử.

Giữ chế độ `DRAFT_REVIEW`: kiểm tra nội dung dự thảo đã cung cấp, tách khỏi việc ký,
thanh toán thực tế, bàn giao, quyền sở hữu thực tế và hồ sơ bên ngoài. Không thêm
chữ ký, biên nhận, nguồn pháp luật giả hoặc tự chuyển output thành HUMAN_VERIFIED.

## 2. Người 2: hồ sơ và dữ kiện có nguồn

Extractor `rules-v8` bổ sung hai binding, vẫn giữ quote/offset của active chunks:

| Dữ kiện | Cách xác định | Consumer và giới hạn |
|---|---|---|
| `profile.co_thoa_thuan_trong_tai=False` | Bộ dự thảo được khai báo đủ, mọi trang có text, có điều khoản chọn Tòa án và không có từ “trọng tài” trong toàn bộ nguồn | Scope Resolver loại nhánh trọng tài khỏi **bộ dự thảo đã cung cấp**. Không xác nhận rằng các bên không có thỏa thuận trọng tài riêng bên ngoài. |
| `maintenance_base_reference=STATED_SALE_PRICE` | Phụ lục ghi rõ khoản bảo trì dùng cùng phạm vi giá đã nêu | Verifier có thể kiểm tỷ lệ trên giá trị được dự thảo khai báo; không tự chứng nhận giá trước thuế/phí theo hồ sơ thực tế. |

Suy luận trọng tài mang `DERIVED_REVIEW_PENDING`, method
`COMPLETE_DRAFT_COURT_ONLY_V1`, `human_verified=False`. Nó chỉ được dùng trong
extraction cho bộ dự thảo đủ nguồn. FULL_ASSESSMENT, nguồn thiếu trang/phụ lục hoặc
có nhắc trọng tài vẫn không được suy từ “không tìm thấy” thành false. Cùng một PDF
nhưng mục đích/coverage khác có extraction identity khác, tránh dùng lại facts sai.

Không cần sửa PDF để thêm các control fields này. Không phải mọi hợp đồng mới đều
khớp hai pattern; trường hợp khác tiếp tục cần extraction hoặc review có căn cứ.

## 3. Người 3 và 5: dùng đúng mốc C01 → C05

C01 đã có `moc_ap_dung` và `loai_moc_ap_dung`; trước đây resolver chưa dùng chúng.
Bây giờ workflow truyền persisted C01 vào `CatalogTemporalResolver(case=case)`.

- Chỉ dùng mốc khai báo nếu loại mốc khớp chính xác với yêu cầu, sau chuẩn hóa alias.
- Không lấy ngày ký/today thay TEMPLATE_USE hoặc mốc sự kiện thu tiền.
- Nếu C02 có ngày cùng loại nhưng khác C01: giữ UNKNOWN, không âm thầm ghi đè.
- C05 lưu nguồn khai báo riêng tại `nguon_snapshot_json.assessment_marker`:
  actor, case, loại, ngày và basis; `moc_id=None` vì đây không phải mốc trích từ PDF.
- DRAFT_REVIEW ghi basis `PLANNED_DRAFT_SCENARIO`; đó là thời điểm dự kiến do người
  gọi khai báo, không phải chứng minh mẫu đã được dùng hoặc hợp đồng đã ký.
- Handoff kiểm lại case/contract/actor/date/basis với C01 trước downstream.

Trong demo này người gọi chọn rõ **TEMPLATE_USE, 16/02/2017**, là giả định thời điểm
rà soát mẫu synthetic. Ba family cần mốc này được phân giải bằng khai báo đó;
không phải extractor tự suy ra ngày sử dụng mẫu từ ngày ký.

UI bổ sung lựa chọn TEMPLATE_USE cùng lời giải thích. Không thêm field schema,
cột workbook hoặc migration DB mới cho thay đổi này.

## 4. Người 4: kiểm tra điều kiện trước khi kiểm tra đáp ứng

Policy máy đọc [draft_review_policy.json](../contracts/draft_review_policy.json)
chứa `local_conditions`; implementation nằm trong `conditional_review.py`.

| Criterion | Điều kiện phải kiểm | Kết quả khi điều kiện không phát sinh |
|---|---|---|
| DS418_01/02 | Có thỏa thuận phạt vi phạm | NOT_TRIGGERED, không phải SATISFIED |
| DS435_02 | Không có thỏa thuận về địa điểm giao tài sản | Có địa điểm đã thỏa thuận thì nhánh mặc định không phát sinh |
| DS442_02 | Không có thỏa thuận rõ về chi phí vận chuyển/chuyển quyền sở hữu | Có thỏa thuận chi phí thì nhánh mặc định không phát sinh; Điều 442 là **chi phí**, không phải chất lượng |
| DS452_01/02 | Có thỏa thuận dùng thử trước khi quyết định mua | Không có dùng thử thì NOT_TRIGGERED |
| DS453_01/02 | Có thỏa thuận cấp thời hạn trả chậm/trả dần sau nhận tài sản | Lịch ứng tiền xây dựng hoặc giữ lại phần chờ giấy chứng nhận tự nó chưa xác lập giao dịch này |

DS444_02 có binding riêng cho **nội dung phân bổ trách nhiệm**, không yêu cầu dự
thảo chứng minh trạng thái nhận thức của bên mua hoặc quyền sở hữu đã xảy ra.
HYC015_02 cũng được đăng ký rõ đích CONTRACT_CONTENT; không áp mặc định cho mọi
criterion có điều kiện.

Rà toàn văn đọc mọi active chunk theo ma trận source × criterion. Câu hỏi điều
kiện được tách khỏi predicate tuân thủ: PRESENT/ABSENT/UNCERTAIN trước, rồi mới
suy ra MATCH/NO_MATCH/UNKNOWN theo policy của từng criterion. Nhánh mặc định có
chiều đảo rõ ràng: tìm thấy thỏa thuận chi phí tức nhánh không-thỏa-thuận NO_MATCH.

Thiếu một ô ma trận hoặc nguồn lạ thì không tạo proof. NO_MATCH chỉ được chấp nhận
khi có artifact đầy đủ, hash và provenance đúng run. C07 giữ UNKNOWN + excluded;
C08 dùng `assessment_disposition=NOT_TRIGGERED`. Không thêm enum pháp lý giả và
không tính những trường hợp đó thành đáp ứng. MATCH vẫn phải qua semantic reasoning,
quote, rules, ngoại lệ và numeric như bình thường.

## 5. Numeric bảo trì và ngoại lệ phạt

### Tỷ lệ bảo trì HYC049_02

Verifier chỉ bind khi có giá bán dạng money, số tiền bảo trì có currency, phần
trăm được ghi rõ và dẫn chiếu mẫu số cùng phạm vi. Decimal kiểm số tiền/giá/phần
trăm nhất quán, sau đó rule đã pin kiểm ngưỡng. Tỷ lệ khác ngưỡng có thể VIOLATED;
con số mâu thuẫn, thiếu đơn vị hoặc thiếu mẫu số không được tự coi là hợp lệ.

Các field legacy `numeric_target_reviewed` và `denominator_definition_reviewed`
ở nhánh này có nghĩa backend đã đối chiếu nguồn theo policy dự thảo, kèm reference
`BACKEND_STATED_CONTRACT_RATIO_V1:<source SHA>` và authority
`BACKEND_SOURCE_CHECK_DRAFT_ONLY`. **Không phải người thật đã duyệt**. Phạm vi mẫu
số `STATED_CONTRACT_VALUE_ONLY` chỉ đánh giá tỷ lệ dự thảo khai báo, không chứng
nhận cơ sở tính tiền đã nộp. FULL_ASSESSMENT không được dùng binding hạn chế này.

### Ngoại lệ DS418_02

Chỉ xử lý adapter `EX_DS418_SPECIAL` cho đúng nhánh căn hộ, chủ đầu tư bán cho cá
nhân tiêu dùng, ngày nằm trong hiệu lực nguồn chuyên ngành đã pin. Evidence pháp
lý bổ sung là Điều 16 Luật Kinh doanh bất động sản 2014 trong knowledge snapshot;
không mượn trần phạt thương mại 8% để áp cho mọi hợp đồng. Sai regime hoặc thiếu
nguồn thì ngoại lệ vẫn unresolved. LLM nhận cả nguồn liên quan, không chỉ nguồn
chính của criterion.

Nguồn đối chiếu cho adapter: [Bộ luật Dân sự 2015 — bản Chính phủ](https://datafiles.chinhphu.vn/cpp/files/vbpq/2016/01/91_.pdf)
và [Luật Kinh doanh bất động sản 2014 — CSDL văn bản pháp luật](https://vbpl.vn/bogiaoducdaotao/Pages/ivbpq-toanvan.aspx?ItemID=46749&Keyword=).
Các adapter chỉ chạy với source/version đã pin; tài liệu này không mở rộng kết luận
sang giao dịch hiện tại thuộc chế độ pháp luật khác.

## 6. Semantic và bàn giao evidence

- Full-document reviewer đọc `articles.noi_dung_nguon`, fallback `noi_dung` cho
  catalog legacy. Trước bản sửa, lookup chỉ dùng key legacy có thể làm mất nội
  dung căn cứ pháp luật trong prompt rà toàn văn.
- HYC011 phân biệt nghĩa vụ thanh toán bình thường/không chờ thông báo với nghĩa
  vụ vẫn buộc thực hiện khi bên bán vi phạm.
- HYC012 phân biệt bên bán tự chuyển hợp đồng mua bán với bên mua chuyển nhượng
  hoặc chuyển hợp đồng dịch vụ quản lý cho Ban quản trị.
- `TC_PV_DS446_02` mô tả mốc/thời hạn nhưng không lặp chữ bảo hành. Retrieval
  nay có binding ID → warranty_months/warranty_start, thay vì chọn đoạn giá chỉ
  theo từ khóa. C07 nhận thêm Điều 85 Luật Nhà ở 2014 khi nguồn đó có hiệu lực
  tại mốc của yêu cầu; không gán Điều 85 của luật khác chỉ vì trùng số Điều. Nguồn: [Luật Nhà ở 2014](https://vbpl.vn/FileData/TW/Lists/vbpq/Attachments/46742/VanBanGoc_65_2014_QH13.pdf).
- Môi trường k3d đặt ASSESSMENT_LLM_MAX_CONTEXT_CHARS=120000, vì hai criterion
  quyền/nghĩa vụ có gói khoảng 93–95 nghìn ký tự sau biểu diễn nguồn gọn. Không
  cắt evidence để ép vừa 80 nghìn; ngân sách này là theo model/môi trường, không
  tự đổi default cho mọi provider.
- C06 từ rà toàn văn quay lại đúng criterion trước C07. LLM không được tự trả gates
  hoặc tạo review của con người. Prompt full-review V4 và semantic V9 giữ phiên bản.

## 7. Trách nhiệm khi năm người tiếp tục làm song song

| Người | Phần cần giữ khi thay implementation |
|---|---|
| 1 | Giữ source/knowledge SHA; đổi PDF hoặc catalog phải tạo revision và đánh giá lại. Bản sửa code này không phát hành lại workbook/đáp án tham chiếu. |
| 2 | Fact mới phải có active quote/offset, provenance và extraction identity. Không biến null thành false hoặc dấu trống thành chữ ký. |
| 3 | C05 giữ source C01/C02 phân biệt, đúng loại mốc. C06 không dùng evidence của run/extraction khác. |
| 4 | Mỗi condition/ngoại lệ/numeric có binding rõ ràng. NO_MATCH không phải đáp ứng; thiếu adapter phải hiện diagnostic. |
| 5 | Persist C01 trước workflow, truyền case vào resolver, hiển thị NOT_TRIGGERED/outside riêng; report cũ đóng băng, publish cần C12. |

## 8. Chạy lại và giới hạn

Dùng backend/API/worker cùng image mới, frontend mới. DB đã có migration 0008 thì
không cần seed lại hoặc thay dataset để dùng code này. Tạo case mới; chọn rà soát
dự thảo, khai báo bộ tài liệu đã cung cấp đủ và chỉ nhập mốc khi biết ý nghĩa của nó.

Đây là kiểm tra E2E một PDF baseline có text layer. Không thay nghiệm thu toàn
bộ 360 PDF, OCR/DOCX, mọi nhánh luật/numeric hoặc đăng nhập/phân quyền production.
Những citation chưa định danh đủ vẫn UNKNOWN. DRAFT/PENDING không phải bản đã được
review và phát hành cho khách hàng.

## 9. Kết quả chạy thật sau bản sửa cuối

- Case `CA_UP_3875AC53FBAF`.
- Run `RUN_3ee1dec5fa634fb1906e5b4c8eaf6506`.
- Report `REPORT_0fe8bebb-33dd-51fd-a254-d3e11b8b335d`.
- [Mở tab Tuân thủ](http://app.legal-checker.localhost:18880/reports/REPORT_0fe8bebb-33dd-51fd-a254-d3e11b8b335d?tab=compliance).
- PDF SHA `9bac4ac8ae4a2e71584c8b421bce6106b3a3cec54061bfc678e869f2430b8e97`.
- Knowledge SHA `32d59bcb9efe506389543bae5ee819d2d07d4a322425fa2d3ffa377c1eff698b`.
- Mục đích DRAFT_REVIEW, đủ bộ tài liệu được cung cấp; TEMPLATE_USE dự kiến
  16/02/2017 do người gọi khai báo trong C01. Không dùng reference replay.

| Phần | Kết quả hiển thị của run cuối |
|---|---|
| Documents | 78 trang, 139 chunks, 56 facts |
| C05 | 75 CONFIRMED, 248 NOT_APPLICABLE, 0 UNKNOWN |
| C07 | 83 đáp ứng, 39 ngoài phạm vi dự thảo, 6 không áp dụng theo điều kiện, 1 chưa xác định |
| C08 | 58 tuân thủ nội dung, 14 ngoài phạm vi, 2 không phát sinh điều kiện, 1 chưa đủ căn cứ |
| NON_COMPLIANT / PARTIAL | 0 trong run này |
| C09 | 5 VALID, 7 UNKNOWN |
| C10/C11 | 8 mục cần xác minh và 8 khuyến nghị liên kết |
| Rà toàn văn | 55 criteria × 139 chunks, 4 nhóm nguồn |

Raw C07 vẫn là 83 SATISFIED + 46 UNKNOWN. Trong 46 UNKNOWN có 39 outside và
6 excluded theo điều kiện; chỉ **1** chưa kết luận thật sự. Raw C08 là 58 COMPLIANT
+ 17 INSUFFICIENT; 17 này gồm 14 outside + 2 NOT_TRIGGERED + **1** NEEDS_EVIDENCE.
UI đọc disposition đã lưu để phân biệt, không sửa enum pháp lý.

So với run lịch sử ở tài liệu v3: yêu cầu thiếu căn cứ thực sự từ **17 → 1**,
C05 chưa phân giải từ **8 → 0**. Phạm vi kết quả thay đổi theo C05 đã phân giải;
đây là kết quả một run, không phải metric accuracy toàn bộ dataset.

Các điểm kiểm chứng trực tiếp:

- DS446_02 SATISFIED với quote 60 tháng/mốc nghiệm thu từ trang 18 và phụ lục
  trang 77, không còn chỉ nhận đoạn về giá.
- HYC024_01/02 SATISFIED với Điều 5/6 quyền và nghĩa vụ tại trang 9–13; không còn
  dừng trước LLM vì CONTEXT_LIMIT.
- HYC035_01 SATISFIED với lịch dự kiến gắn tiến độ trong phụ lục trang 77; không
  xác nhận đã thu tiền hoặc tiến độ xây dựng thực tế đã đạt.
- Phạt, phân bổ trách nhiệm, tỷ lệ bảo trì và hai điều khoản cấm trước đây UNKNOWN
  đã có kết quả; dùng thử/trả chậm và các nhánh mặc định không phát sinh có proof
  riêng, không bị tính thành SATISFIED.

### 9.1 Một mục UNKNOWN còn lại nghĩa là gì?

`TC_PV_HYC015_02`, thuộc FAM_GENERAL_TERMS_DISCLOSURE: chưa xác định được văn bản
**điều kiện giao dịch chung** cùng thời điểm áp dụng tương ứng từ đầu vào hiện có.
Cần cung cấp văn bản/điều khoản tương ứng hoặc review có căn cứ xác định nội dung
nào trong hồ sơ là điều kiện giao dịch chung và thời điểm áp dụng của nó. Không
được lấy một ngày có sẵn trong hồ sơ để mặc định đáp ứng criterion.

C01 TEMPLATE_USE đã giải quyết **chọn phiên bản luật**. Nó không tự tạo evidence
chứng minh nội dung công bố hoặc thời điểm áp dụng được ghi trong văn bản giao dịch
chung. Một câu “hợp đồng có hiệu lực” cũng không tự được đồng nhất với mọi văn bản
điều kiện giao dịch chung chưa định danh. Đây là giới hạn kết luận hiện tại, không
phải lời khẳng định đã kiểm chứng nguồn hoàn toàn không có bất kỳ nội dung tương tự.

Bảy citation UNKNOWN vẫn cần định danh/nguồn theo nhiệm vụ người 3; bản sửa này
không tự gán số hiệu văn bản hoặc chuyển chúng thành VALID.

### 9.2 Kiểm tra và trạng thái triển khai

- Backend: **1.607 passed, 7 skipped**. Test mới kiểm court-only draft, không suy
  absence từ đọc thiếu ma trận, condition ba trạng thái/chiều đảo, numeric thiếu
  mẫu số/conflict/FULL, phạm vi ngoại lệ và xung đột/sai loại mốc C01.
- Ruff lint/format pass; frontend TypeScript/Vite build pass.
- Tám tab mở thành công, 0 JavaScript error và 0 HTTP error trong browser.
- JSON/PDF export trả 200; JSON khớp report lưu DB, PDF có định dạng PDF hợp lệ.
- **285 quote** khớp active chunk/offset; **323 C05 receipts** khớp
  case/run/contract/source/knowledge/policy. Risk/recommendation không nối nhầm run.
- PDF backend phục vụ đúng SHA nguồn. Report giữ DRAFT/PENDING; không tạo sự kiện
  human review, publish hoặc kịch bản biên nhận thực thu giả định.
- Diagnostics cuối không còn VERIFICATION_PROVIDER_NOT_CONFIGURED, NO_SELECTED_C06,
  CONTEXT_LIMIT, CALL_LIMIT, INVALID_SCHEMA, INVALID_BATCH_RESPONSE hoặc lỗi matrix.
- Audit: 20 full-document success + 16 semantic success + 5 repair success; có
  1 RATE_LIMIT tạm thời đã retry. Các lượt repair/HTTP success không được dùng
  thay kiểm tra kết luận/quote; diagnostics cuối đã được kiểm riêng.
- 16 report có trước lượt sửa này giữ nguyên raw JSON/checksum. Hai run demo mới
  tạo thêm hai report; không đổi workbook, PDF, knowledge hoặc seed baseline.

API/worker/scheduler chạy backend image `478b0435…`; frontend `1495a522…`.
Deployments Ready; số replica API do HPA 2–4 quản lý. Đây là build từ worktree local,
chưa commit/push hoặc phát hành GHCR. Hai Argo apps Healthy/OutOfSync; auto-sync
đang tạm dừng cho bản local, không gọi đây là GitOps Synced. Thay đổi ngân sách
120000 nằm trong repo GitOps local để dựng lại được.

Bằng chứng riêng tư nằm trong
`data/private/remaining_verification_fix_20261109/live_run_final/`: report/draft,
comparison, audit, ảnh tám tab, lineage checks và exports. Không commit thư mục này.

## 10. Bản sửa tiếp theo

Các con số ở mục 9 là kết quả run lịch sử. Bản sửa tiếp theo xử lý extraction/identity
viện dẫn và evidence của HYC015_02 tại [biên bản viện dẫn/GTC](citation_and_general_terms_fix_20261109.md).
Không dùng backlog của run cũ để khẳng định trạng thái run mới.
