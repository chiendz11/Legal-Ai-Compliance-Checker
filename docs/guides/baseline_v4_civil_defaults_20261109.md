# Baseline PDF v4 và sửa cách đánh giá mặc định dân sự

Revision code/knowledge: `V750_CIVIL_DEFAULTS_20261109`.
Revision PDF: `PDF360_DRAFT_GTC_V4_20261109`.
Chế độ nghiệm thu: `DRAFT_REVIEW`, không xác nhận đã ký hay đã thực hiện giao dịch.

Cập nhật gói nguồn: `PDF360_DRAFT_GTC_V4_R2_20261110`. Xem
[biên bản ngày 10/11](baseline_v4_acceptance_20261110.md) để biết kết quả run mới,
sửa tên chủ thể, Unicode và producer `rules-v10`. Các số trang giữ từ v3 bên dưới
là kết quả r1; r2 tái dựng phụ lục synthetic có log, giữ nội dung/bố cục/hình ảnh
phần mẫu nguồn và kiểm riêng các ô synthetic được sửa.

## 1. Vấn đề đã xác định từ ca thật

Hai kết quả trong báo cáo trước cần hai cách sửa khác nhau:

| Mục | Nguyên nhân | Thay đổi |
| --- | --- | --- |
| `TC_PV_DS436_01` — phương thức giao | C06 chọn Điều 16 về Fax/thư, bỏ Điều 8 giao nhận | Sửa source anchors, lấy tiêu đề trên nguyên văn thay vì chuỗi index đã thêm đường dẫn; mở ngữ cảnh cha/con có giới hạn |
| `TC_PV_DS453_02` — bảo lưu sở hữu/rủi ro | Rule lẫn điều kiện phạt/hủy/chấm dứt; model suy diễn bảo lưu là vi phạm | Thu hẹp predicate đúng Điều 453; tách điều kiện mua chịu khỏi hậu quả được luật cho phép; giới hạn kết luận về thực hiện bằng chứng cứ thực hiện |
| `TC_PV_HYC015_02` — mốc áp dụng điều kiện chung | Nội quy quản lý có mốc riêng; model không ổn định khi đồng nhất nội quy với điều kiện bán hàng | Làm rõ bộ điều kiện giao dịch chung và ngày dự kiến áp dụng ngay trong PDF synthetic, không thêm một đường tắt SATISFIED trong backend |

Đối chiếu nguồn chính thức:

- [BLDS 91/2015/QH13](https://vbpl.vn/van-ban/chi-tiet/bo-luat-dan-su-so-91-2015-qh13--95942): Điều 436 cho phép thỏa thuận phương thức giao; khi không thỏa thuận có mặc định giao một lần, trực tiếp. Điều 453 cho phép bảo lưu sở hữu, có xét thỏa thuận khác.
- [Luật 66/2014/QH13](https://vbpl.vn/van-ban/chi-tiet/luat-kinh-doanh-bat-dong-san-so-66-2014-qh13--46749): Điều 57 có cơ chế giữ lại tiền đến khi được cấp giấy chứng nhận. Nhiều đợt ứng trước hoặc phần giữ lại này tự nó chưa chứng minh mua chịu theo Điều 453.
- [Luật 59/2010/QH12](https://vbpl.vn/van-ban/chi-tiet/luat-bao-ve-quyen-loi-nguoi-tieu-dung-so-59-2010-qh12--26356): Điều 18(2) yêu cầu xác định rõ thời điểm áp dụng điều kiện giao dịch chung.
- [Luật 19/2023/QH15](https://vbpl.vn/van-ban/chi-tiet/luat-bao-ve-quyen-loi-nguoi-tieu-dung-so-19-2023-qh15--161263): Điều 27 tách nội dung mốc áp dụng và việc công khai; không dùng số Điều 18 của luật cũ cho kịch bản sau khi luật mới có hiệu lực.

Đây là diễn giải có đối chiếu nguồn cho phạm vi hẹp. Không suy ra rằng mọi điều khoản
bảo lưu, mọi lịch thanh toán hay toàn bộ 90 baseline đều đã được thẩm định pháp lý.

## 2. Code và bàn giao giữa người 3–5

Retrieval giữ nguyên `Chunk.noi_dung` cho quote/offset. Đường dẫn Điều/Phụ lục chỉ
phục vụ index. Source anchor chạy trên chunk nguyên văn; C06 ghi riêng score
`source_anchor`, parent context và phiên bản `SOURCE_ANCHORS_V2` để truy vết.
Một anchor là ứng viên cần đọc, không phải kết luận tuân thủ.

Với kiểm tra sự hiện diện của nội dung bắt buộc, full-document review có thể tìm
thấy hàng chục đoạn nhắc đến cùng chủ đề. C06 giữ toàn bộ ứng viên và artifact đọc
toàn văn, nhưng chỉ chọn tối đa sáu đoạn đại diện để đối chiếu ngữ nghĩa, ưu tiên
tiêu đề đúng chủ đề. Không áp dụng giới hạn này cho điều khoản cấm; không biến
các đoạn bị bỏ chọn thành chứng nhận vắng nội dung. Thay đổi xử lý lỗi context
overflow đã thấy ở `TC_PV_HYC044_02`, thay vì cắt nguồn âm thầm hay tăng budget tùy ý.

Full-document reviewer hỏi riêng điều kiện phát sinh. Với Điều 453, câu hỏi là có
thỏa thuận trả chậm/trả dần sau nhận tài sản hay không, không lấy predicate về bảo
lưu làm câu hỏi tìm kiếm. `PRESENT/ABSENT/UNCERTAIN` ở bước này chưa phải kết quả C07.

Decision-rule JSON có trường tùy chọn `allowed_evaluation_targets`:

```json
{
  "conclusion_scope_required": true,
  "performance_requires_receipt_evidence": true,
  "allowed_evaluation_targets": ["PERFORMANCE"]
}
```

Đối với nhánh `VIOLATED` của đúng hai tiêu chí DS436_01 và DS453_02, predicate đã
được giới hạn vào vi phạm thực hiện nghĩa vụ xác định được. C07 chỉ nhận nhánh này
khi target được backend xác minh và có chứng cứ thực hiện đăng ký đúng context.
Đoạn điều khoản dự thảo tự nó không được dùng thay chứng cứ thực hiện. Các tiêu chí
về điều khoản cấm hoặc quy định bắt buộc khác vẫn đánh giá riêng, không bị vô hiệu.

Allowlist sai/thiếu scope policy bị từ chối. Việc từ chối một đề xuất không tự đổi
thành SATISFIED. Nhánh SATISFIED vẫn cần nguồn, scope/version, evidence và exceptions.
Schema máy đọc: [decision_rule_policy.schema.json](../contracts/decision_rule_policy.schema.json).

## 3. PDF v4 sửa gì và giữ gì

Tạo từ PDF v3, giữ toàn bộ trang và hình ảnh cũ; v2/v3 không bị ghi đè.

- Điền thêm vùng trống có nhãn rõ, như dự án và tháng/năm bàn giao dự kiến. Chỉ mở
  rộng ngang trong khoảng trắng an toàn, không thu nhỏ chữ dưới 9,5 pt hoặc che
  nội dung/hình ảnh. Vùng không đủ chỗ vẫn được ghi log để xử lý riêng.
- Chỉ điền thông tin chủ thể khi xác định được vai trò và nhánh cá nhân trong phần
  các bên; không mang vai trò của đầu hợp đồng sang mọi phụ lục phía sau.
- Thêm `PHỤ LỤC 02 — ĐIỀU KIỆN GIAO DỊCH CHUNG`, xác định phạm vi, phiên bản và mốc
  dự kiến áp dụng. Đây là **bổ sung thỏa thuận**, không gọi là chỉ điền ô trống.
- Nội quy quản lý và điều kiện bán hàng được phân biệt. Phụ lục không nói rằng đã
  thực hiện việc niêm yết/công khai, đăng ký mẫu hoặc ký kết.
- Với biến thể thiếu ngày, phụ lục mới giữ mốc là chưa cung cấp; không làm lộ ngày
  qua phần bổ sung. Biến thể bất lợi và mâu thuẫn giữ mục tiêu kiểm thử riêng.
- Không tạo chữ ký, con dấu, giấy phép, phê duyệt cơ quan hoặc biên nhận thật.

Metadata từng PDF có `previous_pdf_sha256`, `v4_inline_changes`,
`substantive_amendments_v4`, vị trí phụ lục và checksum mới. Các trường hợp không
điền được có reason. Mọi file vẫn ghi `legal_gold=false`.

## 4. Rà 90 baseline có ý nghĩa gì?

Đã đọc cả 90 baseline v3 bằng công cụ đọc PDF độc lập với parser/reasoner của app.
1.080 kiểm tra về hash, dữ liệu cơ bản, phép tính giá/diện tích/bảo trì, mốc bảo hành,
loại nhà ở và trạng thái dự thảo đạt trong phạm vi đó. Có 6 mẫu NOXH, được giữ loại.

Phát hiện 7.206 placeholder nguồn. Đây là số token trong text layer v3, không phải số ô trắng nhìn thấy hoặc số lỗi bắt buộc:
có nhánh người mua tổ chức không chọn, giấy phép/dữ liệu dự án chưa có, lịch biểu,
ô giao dịch và những vai trò chưa xác định. Không điền chúng bằng một dữ liệu dùng
chung. Dấu chấm được phủ khi điền trực quan có thể vẫn được parser nhận ra trong
text layer; metadata vùng điền giúp phân biệt với nội dung còn thiếu thật. Trong 453 số hiệu viện dẫn được dò ở thân hợp đồng, 33 nằm ngoài/chưa rõ
khoảng hiệu lực và 51 chưa tìm thấy trong catalog theo số hiệu chính xác. Đây là
danh sách cần xét ngữ cảnh/lịch sử, chưa phải 84 vi phạm đã xác nhận.

V4 được kiểm lại với 1.440 kiểm tra nguồn/dữ kiện trên 90 baseline, đều pass.
Toàn bộ 360 PDF giữ 18.300 trang v3 và 2.168 lượt hình ảnh; có 407 lần điền trực
tiếp, 136 vùng mở rộng an toàn, 72 vùng ghi nhận không đủ chỗ. Phần mới vẫn là
source-checked targeted amendments, không phải full-catalog gold.

Workbook rà soát phân biệt kiểm tra nguồn với đáp án pháp lý. Không dùng output
production làm gold cho chính production. Reference HD360_001 được viết trước
lần chạy mới; chỉ kết luận trong phạm vi các tiêu chí và nguồn được nêu.

## 5. Đồng bộ knowledge cho DB local

Không ghi đè snapshot cũ. Parent của revision này:

```text
32d59bcb9efe506389543bae5ee819d2d07d4a322425fa2d3ffa377c1eff698b
```

Snapshot mới:

```text
3b8f12a619f8ab017d7d71957d5e07ded651d75f8205a8dbe338abe402ed7042
```

Với DB đã có TEAM baseline và revision runtime 08/11:

```bash
python -m scripts.local_db align-content-defaults \
  --parent-sha256 32d59bcb9efe506389543bae5ee819d2d07d4a322425fa2d3ffa377c1eff698b
```

DB mới chưa có revision runtime thì seed TEAM theo hướng dẫn hiện hành, chạy
`python -m scripts.local_db align-runtime`, rồi tạo revision trên. Lệnh kiểm tra
parent hash và legal-source binding, không sửa pin của ca/báo cáo lịch sử.

Đổi cấu hình cho ca mới và khởi động lại API/worker:

```dotenv
KNOWLEDGE_SNAPSHOT_SHA256=3b8f12a619f8ab017d7d71957d5e07ded651d75f8205a8dbe338abe402ed7042
DEPLOYMENT_LEGAL_KNOWLEDGE_VERSION=V750_CIVIL_DEFAULTS_20261109
```

Rows sửa được gắn `SOURCE_CHECKED`, không giả mạo người đã review. Bộ kiểm tra
draft có thể dùng nguồn đã đối chiếu; kết quả máy vẫn DRAFT/PENDING.

Workbook `KNOWLEDGE_CIVIL_DEFAULTS_20261109.xlsx` trong gói rà soát là bản xem 18
bảng knowledge và change log, **không phải full runtime workbook để chạy seed**.
Không đổi checksum/manifest tải hiện hành để trỏ nhầm vào workbook này. PDF v4 có
hash khác: output C02/C03, chunks, C06 và downstream từ v2/v3 phải được dựng lại
khi phát hành full dataset tương ứng; không chỉ sửa URL/hash rồi tái dùng evidence cũ.

## 6. Bằng chứng và giới hạn nghiệm thu

Code/backend tại mốc r1: đã chạy trên PostgreSQL test riêng: **1.683 test pass, 7 skip**;
Ruff pass. Các database test ngẫu nhiên tách khỏi DB ứng dụng và được fixture dọn.
1.916 decision rules trong snapshot mới được validate bằng schema JSON; vocabulary
gates đối chiếu với backend. Các tests có nhánh chứng cứ thực hiện hợp lệ, invalid
allowlist, nguồn/run sai và không chấp nhận clause thay receipt.

Local k3d dùng cùng backend image cho API/worker/scheduler. E2E upload PDF thật,
chạy module thật, mở tám tab và export JSON/PDF/DOCX; không reference replay,
không tự review hoặc publish. Giữ checksum báo cáo cũ để so sánh sau rollout.

Các biên bản/chỉ số từng run nằm trong private evidence ngoài Git. Kết quả k3d
không phải CI đã publish, và pass một PDF không chứng minh cả 90 baseline đạt toàn catalog.

## 7. Kiểm độc lập evidence trước đề xuất vi phạm

Run v4 phát hiện một đề xuất nói về miễn trách nhiệm của bên bán nhưng lại trích
một dòng về Ban quản trị. Quote có thật chưa đủ chứng minh predicate. Luồng tích
hợp bật `verify_adverse_evidence=True`: đề xuất VIOLATED do LLM phải qua một lượt
kiểm tra riêng, chỉ đọc chính các câu được viện dẫn, rule đã pin, chủ thể, điều
kiện và ngoại lệ. Không lấy giải thích của proposal làm bằng chứng.

Verdict chỉ có SUPPORTED/UNSUPPORTED/UNCERTAIN. SUPPORTED phải nêu IDs của quote
thật; IDs lạ/trùng/không có quote đều bị từ chối. Hai verdict còn lại tạo UNKNOWN
với `ADVERSE_EVIDENCE_NOT_SUPPORTED`, giữ proposal gốc để review. Không tự đổi
thành SATISFIED. Kết quả kiểm vẫn là máy, không phải human approval; backend vẫn
kiểm tất cả gates và số liệu. Nhánh numeric do backend kiểm không cần LLM xác minh
lại phép tính. Replay adverse không tự mang lại xác nhận mới.

Audit LLM dùng prompt `C07_ADVERSE_EVIDENCE_V1`; analysis lưu policy, model, request
ID, input hash và verdict. Đây là một lượt kiểm evidence bổ sung, không được gọi
là bảo đảm mọi kết luận pháp lý đúng. Các UNKNOWN hoặc false-positive mới của
những criterion khác phải được công bố trong biên bản chạy, không giấu bằng cách
chọn lại một run có số lượng tuân thủ đẹp hơn.

## 8. Bổ sung ngày 10/11: tài khoản bảo trì không còn rơi mất ở C02

PDF đã có ba dòng số/tên/ngân hàng tài khoản bảo trì, nhưng producer cũ chỉ nhận
cách ghi một dòng có dấu `;`. `documents.rules-v10` đọc cả hai dạng, giữ quote đầy
đủ nhãn và giá trị, không lấy tài khoản thu tiền mua căn hộ thay thế. Có nhiều
giá trị thì giữ CONFLICT, không chọn dữ liệu thuận lợi.

`C07_EXACT_CONTENT_V3` kiểm `TC_ACCOUNT_2015_03` trong đúng version 2015 khi đủ
ba facts nguồn, selected C06 và mọi gates/context. Giá trị trống/placeholder,
UNKNOWN, nhãn tài khoản thanh toán, fact sai quote hoặc xung đột không được nhận.
Đây chỉ là kiểm những trường đã ghi trong dự thảo. Không tạo xác nhận ngân hàng
có giấy phép, tài khoản đã mở, đúng chủ tài khoản hoặc đã thu tiền thực tế.

Đã chạy preflight từ chính bytes HD360_001 v4, không gọi LLM và không ghi DB:
C02 có đủ ba facts, C07 trả SATISFIED kèm ba quote/offset. PDF và knowledge hash
được giữ nguyên; thay đổi producer làm extraction/chunk IDs mới để bảo toàn lineage.

`rules-v10` bổ sung tên nhiều dòng và nhãn có khoảng trắng kép do PDF căn đều.
Việc nối giá trị có giới hạn trong cùng chunk và kết thúc ở nhãn tài khoản kế
tiếp; không ghép chú thích hoặc dữ kiện thiếu vào tên. Kết quả rà corpus và run
thật được công bố tại biên bản ngày 10/11, tách khỏi kiểm tra nguồn độc lập.
