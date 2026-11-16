# Xử lý nốt 12 trường hợp trong demo HD360_001 — 08/11/2026

## Phạm vi

Tiếp nối [báo cáo vòng trước](hd360_followup_verification_20261108.md). Thay đổi gồm
code, một catalog revision bất biến và một bản PDF demo có phụ lục bổ sung.
Không ghi đè báo cáo/snapshot cũ, không sửa đồng loạt 360 PDF hoặc phát hành lại
expected DEV/VAL/TEST cũ dưới tên revision mới.

## 1. Năm trường hợp không phát sinh điều kiện

AGG_CAN_HO_V1 được giữ nguyên: C08 gốc của yêu cầu không còn criterion bắt buộc
vẫn là INSUFFICIENT. Metadata NOT_TRIGGERED đã có được dùng nhất quán cho tổng
quan, biểu đồ, thẻ requirement, lịch sử, lọc và export. Đây là trình bày disposition
backend đã lưu, không suy đoán một kết luận COMPLIANT mới.

C13 thêm `overall_summary.requirement_display_statuses` và
`criterion_display_statuses`. Giá trị C08 gốc và finding C07 gốc vẫn giữ trong
records. C07 có `excluded=True` được hiển thị riêng thay vì gộp vào số criterion
chưa xác định còn cần xử lý. Người đọc JSON muốn đếm phần cần làm dùng các mảng
display hoặc assessment_disposition, không gộp NOT_TRIGGERED vào thiếu căn cứ.

## 2. Ba trường hợp C05

- Có/không thỏa thuận đặt cọc là dữ kiện riêng với đã/chưa thu tiền. Thêm C02
  `co_thoa_thuan_dat_coc: bool | null`, chỉ trích nhãn nguồn tường minh. Scope mới
  của FAM_APT_DEPOSIT đòi giá trị True; False loại nhánh này, null vẫn UNKNOWN.
- Hai family chỉ có các nguồn hiện đại không còn bị hiểu là nghĩa vụ đã không tồn
  tại trong năm 2017. Catalog ghi rõ family tương đương lịch sử:
  FAM_GYC048 → FAM_TEMPLATE_REGISTRATION;
  FAM_MAINTENANCE_ACCOUNT → FAM_APT_MAINTENANCE_ACCOUNT.
- Resolver chỉ loại nhánh nguồn hiện đại khi ngày trước mọi version của nhánh đó
  và family cũ đã CONFIRMED, đúng khoảng hiệu lực, có source articles được đăng ký.
  Nghĩa vụ cũ vẫn được đánh giá; không mượn một version hiện đại cho hợp đồng cũ.
  Metadata thiếu/sai, family cũ chưa phân giải hoặc khoảng ngày không phù hợp vẫn
  giữ UNKNOWN. C08 kiểm lại proof/hash trước khi chấp nhận loại.

Liên kết lịch sử được đối chiếu với [Quyết định 02/2012 trên Công báo](https://congbao.chinhphu.vn/van-ban/quyet-dinh-so-02-2012-qd-ttg-14128.htm)
và các nguồn Điều 36 NĐ99/2015 đã có trong snapshot. [Cục BVNTD giải thích việc sửa
Điều 36 năm 2021](https://www.bvntd.gov.vn/tintuc_sukien/kinh-phi-bao-tri-khuyen-cao-nguoi-tieu-dung-mot-so-noi-dung-can-luu-y/)
phân biệt chế độ cũ và chế độ sửa đổi. Không tạo văn bản pháp luật hoặc ngày hiệu lực giả.

## 3. Catalog revision và cách áp dụng ở DB local

Mã: `legal_checker.modules.legal_knowledge.runtime_alignment`.
Revision `V750_RUNTIME_ALIGNMENT_20261108`, base snapshot SHA:
`39d823fb72b886d88d55367e928f96a39218d16e4287899fc1a163d25458bc4d`.
SHA mới:
`32d59bcb9efe506389543bae5ee819d2d07d4a322425fa2d3ffa377c1eff698b`.

Revision clone đúng base đã seed, bổ sung metadata của ba family và ghi một
knowledge_snapshots mới có review_status SOURCE_CHECKED. Không UPDATE snapshot
cũ hoặc thay source tables/seed receipt. Chạy nhiều lần cho cùng kết quả.

Sau khi đã seed TEAM DEV/VALIDATION vào DB local:

```bash
source .venv/bin/activate
python -m scripts.local_db align-runtime
```

Lệnh dùng DATABASE_URL từ `.env`; không dán DSN/API key vào Git. Sau đó cấu hình
backend/worker cùng một revision và restart:

```dotenv
KNOWLEDGE_SNAPSHOT_SHA256=32d59bcb9efe506389543bae5ee819d2d07d4a322425fa2d3ffa377c1eff698b
DEPLOYMENT_LEGAL_KNOWLEDGE_VERSION=V750_RUNTIME_ALIGNMENT_20261108
```

Đây là revision cho runtime mới. Fixture/gold cũ tiếp tục pin snapshot cũ để không
đánh giá nhầm khác biệt phiên bản thành lỗi module. Không cần seed lại toàn bộ DB.

Các module dùng `Knowledge(database_url, context.knowledge_snapshot_sha256)` để
đọc đúng revision. Không query source tables rồi coi đó là nội dung của snapshot
mới: các bảng nguồn vẫn chứa baseline, còn revision này lưu bản JSON bất biến trong
`knowledge.knowledge_snapshots`. Mọi output/run tiếp tục pin SHA để truy lại nguồn.

## 4. Bổ sung nguồn cho bốn criterion nội dung

PDF COMPLETE_R4 giữ nguyên 76 trang trước và thêm một trang nguồn synthetic.
Trang mới là một phần đầu vào hợp đồng trong kịch bản, có nhãn dữ liệu hư cấu,
không tạo chữ ký/con dấu hoặc chứng nhận cơ quan thật. Nó ghi rõ:

- Không có thỏa thuận đặt cọc riêng.
- Địa chỉ từng bên; địa chỉ bên mua giữ đúng dữ liệu ở phụ lục trước.
- Vị trí, số thửa, tờ bản đồ và diện tích thửa đất; phân biệt diện tích căn hộ.
- Số tiền và tỷ lệ kinh phí bảo trì phần sở hữu chung.
- Ngày nghiệm thu đưa vào sử dụng, ngày bắt đầu bảo hành và thời hạn bảo hành.

Tên file demo: `HD360_001_COMPLETE_R4.pdf`, SHA-256
`fcc1745ff7552bbbb341385e7acc9b81fecc50f91212103f03fb5f3fcce27dea`.
Đây là bản bổ sung riêng cho demo, chưa thay 360 PDF trên Supabase/Drive. Muốn
tái hiện cùng kịch bản phải upload đúng file này; scenario không áp dụng cho PDF
có SHA khác. Trong repo local file nằm ở
`data/private/finish_hd360_20261108/HD360_001_COMPLETE_R4.pdf` (không commit Git).
Không bật scenario cho hồ sơ khách hàng hoặc hiểu chứng từ synthetic là xác minh
từ một người/cơ quan thật.

Extractor rules-v6 lấy các nhãn này thành C02 facts kèm quote/offset. Thiếu hoặc
mâu thuẫn vẫn không được tự điền. Không suy địa chỉ bên bán từ địa chỉ bên mua.

`content_verifier.py` đăng ký sáu predicate hữu hạn: TC_PV_HYC040_02,
TC_PV_HYC039_02, TC_PV_HYC049_01, TC_PV_DS446_02 và hai tiêu chí thời gian bàn giao
TC_PV_HYC022_01/TC_PV_HYC043_01. Hai tiêu chí sau dùng ngày đã có trong phụ lục,
không tự xem ô tháng/năm trống trong thân mẫu là chưa có ngày bàn giao. Kiểm facts có nguồn thực trong
active chunks, giá trị chuẩn hóa khớp câu nguồn, đủ fields, đúng version/criterion,
ngày bảo hành nhất quán với nghiệm thu. C06 được bổ sung đúng các chunks đó.

Proposal đi qua automatic_review, grounding và reasoner; vẫn đòi verifier,
scope/version/source/exception checks. Backend kiểm sự hiện diện/nhất quán nội dung,
không xác nhận thửa đất/tài khoản hoặc giao dịch tồn tại ngoài thực tế. Kết quả
mang model_version C07_EXACT_CONTENT_V1, không tạo log HTTP LLM giả và vẫn PENDING
human review. Thiếu fact, sai giá trị/quote/offset, conflict hoặc sai run không
được kết luận SATISFIED. Các criterion khác tiếp tục dùng inference bình thường.

## 5. Sửa bước rà toàn văn và kiểm tra đề xuất LLM

Kết quả `PRESENT` của bước rà toàn văn chỉ tạo candidates cho C06. Reasoning tiếp
tục đối chiếu đoạn đó với predicate của criterion trước khi kết luận SATISFIED hoặc
VIOLATED. Đoạn có từ khóa về bảo hành, chẳng hạn, không tự chứng minh có điều khoản
loại trừ nghĩa vụ bảo hành. Nhánh ABSENT vẫn chỉ được dùng khi manifest đủ mọi
chunk/trang đọc được, có xác nhận bộ tài liệu và proof nguồn khớp run/hash.

Đã sửa một lỗi đảo mục tiêu tìm kiếm: trước đây lượt rà điều khoản cấm nhận
predicate của SATISFIED (không có điều khoản cấm), khiến model có thể trả PRESENT
để nói rằng hợp đồng đáp ứng điều cấm. Prompt `C07_FULL_DOCUMENT_REVIEW_V2` lấy
predicate VIOLATED để tìm đúng hành vi bị cấm; nội dung bắt buộc vẫn tìm predicate
SATISFIED. Gói ghi rõ `search_finding`, không đổi nhãn bằng cách dò từ phủ định
trong phần giải thích của model. Kết quả PRESENT vẫn qua semantic C07 như trên.

Proposal SATISFIED/VIOLATED phải có quote hoặc nguồn ngoài đã đăng ký. Với batch,
backend yêu cầu sửa riêng criterion thiếu nguồn tối đa một lần; model chỉ được chọn
ID từ gói đang xét. Sau sửa vẫn thiếu thì trả UNKNOWN với mã
`MISSING_SUPPORTING_EVIDENCE`. Không tự gắn một quote bất kỳ để hợp thức hóa kết luận.
Prompt semantic mới mang phiên bản `C07_SEMANTIC_V4` để phân biệt với lịch sử.

## 6. Trạng thái kiểm chứng

Đã chạy lại bằng UI upload PDF thật qua k3d, mode `modules` và provider Gemini qua
API tương thích OpenAI; không replay output QA:

- Case: `CA_UP_BC19DD8CBAA6`.
- Run: `RUN_98ced670e84d494b8d19c4085732bbca`.
- Report: `REPORT_fa641429-fef5-566d-b3ae-d22031773785`.
- [Mở báo cáo local](http://app.legal-checker.localhost:18880/reports/REPORT_fa641429-fef5-566d-b3ae-d22031773785).

| Phần | Kết quả đã kiểm chứng |
| --- | --- |
| C05 | 75 CONFIRMED, 248 NOT_APPLICABLE, 0 UNKNOWN |
| C07 hiển thị | 103 SATISFIED, 2 VIOLATED, 2 MISSING, 1 UNKNOWN, 21 EXCLUDED |
| C08 hiển thị | 66 COMPLIANT, 3 NON_COMPLIANT, 1 INSUFFICIENT, 5 NOT_TRIGGERED |
| C09 | 5 VALID, 6 UNKNOWN do NAME_ONLY_VERSION_IDENTITY_AMBIGUOUS |
| C10/C11 | 11 risk, 11 recommendation; 4 compliance risk và 7 verification risk |

C07 raw vẫn có 22 UNKNOWN, trong đó 21 có `excluded=True`. C08 raw vẫn có
6 INSUFFICIENT, trong đó 5 có disposition NOT_TRIGGERED. Không sửa enum/đáp án
pháp lý để có các số hiển thị trên. Bốn criterion nội dung ban đầu và hai criterion
ngày bàn giao đều SATISFIED qua C07_EXACT_CONTENT_V1, còn chờ review.

Hai VIOLATED là tỷ lệ thanh toán trước bàn giao và trước cấp giấy trong kịch bản.
Hai MISSING thuộc chữ ký/chức vụ ký; không bổ sung chữ ký/con dấu giả để làm mất
nhãn này. Năm yêu cầu không phát sinh và 21 criterion loại trừ không tạo risk sai.

Một UNKNOWN đang cần xử lý thật: `TC_PV_HYC040_04`, yêu cầu ghi rõ cả diện tích
sử dụng riêng và diện tích sàn xây dựng căn hộ. Text đã trích có định nghĩa hai
loại, và dẫn diện tích sàn sang phụ lục, nhưng chưa xác nhận đủ số liệu từng loại.
Không lấy diện tích thửa đất 10000 m² thay diện tích sàn căn hộ, không tự dùng
624 m² cho cả hai phép đo. Chưa có proof toàn văn riêng cho criterion này nên không
tự đổi UNKNOWN thành MISSING. Sáu citation UNKNOWN chỉ có tên/năm chưa định danh
duy nhất theo policy hiện hành; được giữ trong verification risk, không gán INVALID.

Các kiểm tra đã thực hiện:

- Backend với DB test cô lập: **1562 pass, 7 skip**; Ruff lint/format pass.
- 8 tab report, xem PDF nguồn và export JSON/PDF/DOCX: HTTP 200, không JS/HTTP error.
- Kiểm lại handoff C02–C06, C09, report và nguồn risk/recommendation theo case/run/hash.
- Hash của 186 file Python đang chạy ở API/worker/scheduler khớp source local.
- Một HTTP provider tạm lỗi được retry; hai phản hồi semantic được repair. Không
  còn lỗi cuối CALL_LIMIT/NO_SELECTED_C06/quote mismatch trong run này.
- DB lịch sử cũ giữ 17 run/12 report; report mới là draft, không tạo review events.

Bằng chứng nằm ngoài Git tại `data/private/finish_hd360_20261108/corrected_run/`
(summary, draft/report JSON, coverage artifact, ảnh tám tab và ba bản export).
Hai vòng chạy trước được giữ để đối chiếu lỗi đảo predicate, không ghi đè báo cáo cũ.

Đã deploy image local mới cho API/worker/Beat. Chưa commit/push/publish image;
Argo auto-sync của hai Legal apps đang tạm tắt, Healthy/OutOfSync trong chế độ
apply-local. Không coi đây là Git đã Synced hoặc nghiệm thu độ chính xác pháp lý
trên toàn bộ 360 hợp đồng. Workbook, split và manifest dataset TEAM không đổi.
