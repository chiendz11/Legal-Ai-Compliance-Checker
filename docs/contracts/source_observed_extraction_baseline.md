# Đầu vào và bàn giao Documents theo 90 mẫu đã điền

> Baseline hiện hành cho DB mới: [PDF360 v4 r2 — 10/11](../guides/dataset_pdf360_v4r2_runtime_20261110.md).
> Knowledge được chủ dự án duyệt, hash `4ab2d7ea296ea908e25c09fcb6d5f073f1ebe1917678b36390f803b1c725804a`; full-catalog reference xét 323 families.
> Số liệu PDF/TEAM_CORE của revision trước bên dưới là lịch sử; literal reference mới chưa phải legal gold toàn tài liệu.


Baseline: `SOURCE_FULL90_V2_20261107`. Đọc cùng
[dictionary](data_dictionary.md), [dictionary máy đọc](data_dictionary.json),
[guide người 2](../modules/group_a_document_intelligence.md) và
[INTEGRATION_V1](integration_spec.md).

## 1. Phạm vi đã chốt

360 PDF được sinh từ 90 mẫu nguồn, mỗi mẫu có bốn biến thể. `01_DAY_DU` nghĩa là
đã điền thông tin giao dịch trong các vùng xử lý được của mẫu và phần thông tin
hiện có trong PDF; **không có nghĩa mọi thuộc tính pháp lý đều có giá trị**.

Theo yêu cầu hiện hành, lấy PDF đã điền làm đầu vào cố định. Không viết thêm điều
khoản, giả định sự kiện hoặc tạo chứng từ để đáp ứng một field mà nguồn chưa nêu.
Định nghĩa extractor và điều kiện bàn giao phải dựa trên dữ liệu quan sát được.

Đã đọc mới 90 PDF FULL90, 4.305 trang bằng MuPDF; hash từng file khớp cả manifest
tạo PDF và CASE_MAPPING. Quan sát 19 trường giao dịch ở cả 90/90 bản. Đây là
inventory cấu trúc/nguồn, không phải gold legal labels hoặc chứng nhận mọi clause.
Per-file values, nguồn và split được giữ ngoài Git ở bộ inventory của evaluator.

Nguồn bảo đảm sự có mặt của 19 trường dưới đây là **PHỤ LỤC THÔNG TIN GIAO DỊCH
đã tồn tại ở cuối từng PDF**. Không suy rằng cả 19 trường đều được điền inline
trong thân của cả 90 mẫu. Thân hợp đồng còn placeholder chưa phân loại/ô không
điền được; log của bộ dựng chỉ giúp truy vết, không chứng minh mỗi ô đó là một
thông tin bắt buộc đang thiếu. Không tạo phụ lục hoặc nội dung mới trong đợt rà soát.

Hai lớp quy tắc độc lập:

- Producer chỉ khẳng định điều có nguồn; thiếu thì giữ null/UNKNOWN/candidate.
- Consumer vẫn xét knowledge/checklist đúng phạm vi; **không loại requirement vì
  chưa tìm thấy evidence**, cũng không buộc producer tạo thêm thông tin để có kết luận.

## 2. Mười chín trường đã quan sát trong cả 90 bản

CORE là dữ kiện phải cố gắng chuẩn hóa để phục vụ luồng chung. TARGETED là dữ
liệu đã có, parser/chunker phải giữ nguyên văn; chỉ cần fact riêng khi criterion
hoặc chức năng được giao thực sự dùng nó. Không thêm 19 cột vào ProfileFields.

| Trường thực tế | Bàn giao/route hiện có | Consumer và mục đích | Mức |
|---|---|---|---|
| Số hợp đồng | `facts.so_hop_dong` | Đối chiếu tài liệu/phụ lục, report; khác ID contract/case do backend tạo | CORE |
| Ngày giao kết | `profile.ngay_giao_ket`, fact có nguồn, marker SIGNING | Temporal và bối cảnh citation; giữ raw/precision | CORE |
| Họ tên bên mua | subject BEN_MUA, `facts.ten_ben_mua` | Nhận diện chủ thể, scope và report | CORE |
| Mã định danh bên mua | Chunk/evidence; fact khi criterion cần | Kiểm tra thông tin chủ thể khi có tiêu chí tương ứng | TARGETED |
| Ngày sinh bên mua | Chunk/evidence; fact khi criterion cần | Thông tin chủ thể theo phạm vi; không suy tư cách pháp lý chỉ từ tên | TARGETED |
| Địa chỉ liên hệ bên mua | Chunk/evidence; fact khi criterion cần | Thông tin các bên/thông báo | TARGETED |
| Điện thoại bên mua | Chunk/evidence; fact khi chức năng cần | Liên hệ theo phạm vi; không mặc định là field scope bắt buộc | TARGETED |
| Email bên mua | Chunk/evidence; fact khi chức năng cần | Liên hệ theo phạm vi; không phải chứng minh giao kết điện tử | TARGETED |
| Mã căn hộ | `facts.ma_can_ho` | Nhận diện tài sản, nối đúng evidence | CORE |
| Tầng | Giữ trong `facts.tang_toa`; có thể tách nếu có nguồn | Nhận diện căn hộ | CORE |
| Tòa | Giữ trong `facts.tang_toa`; có thể tách nếu có nguồn | Nhận diện căn hộ | CORE |
| Diện tích sử dụng | `facts.dien_tich` và raw/đơn vị | Đối chiếu mô tả, giá/diện tích khi criterion cho phép | CORE |
| Đơn giá | `facts.don_gia` và raw/đơn vị theo diện tích | Kiểm tra tính nhất quán; không bỏ mất `/m²` | CORE |
| Giá bán căn hộ | `facts.gia_ban`, `profile.gia_tri_hop_dong`, `don_vi_tien` | Facts đầu vào cho reasoning; P4 xác minh mẫu số/thuế/phí trước dùng numeric rule | CORE |
| Giá bán bằng chữ | Chunk/evidence; fact khi criterion cần | Đối chiếu biểu diễn giá khi được đánh giá | TARGETED |
| Ngày bàn giao dự kiến | `profile.ngay_ban_giao_du_kien`, marker EXPECTED_HANDOVER | Cam kết bàn giao, bối cảnh lịch thanh toán | CORE |
| Phương thức thanh toán | `facts.phuong_thuc_thanh_toan` | Đánh giá nội dung điều khoản thanh toán | CORE |
| Ngân hàng nhận tiền | Chunk/evidence; fact khi criterion cần | Thông tin thanh toán; không chứng minh đã thu tiền | TARGETED |
| Tài khoản nhận tiền | Chunk/evidence; fact khi criterion cần | Thông tin thanh toán; không chứng minh đã thu tiền | TARGETED |

Ở FULL90, không lấy được CORE có dòng nguồn là lỗi cần điều tra ở reader/extractor/
mapper. Trên biến thể thiếu hoặc PDF khác, không ép field có giá trị. C02 hiện vẫn
nullable; CORE không biến thành required SQL columns hoặc điều kiện tạo dữ liệu giả.

Giữ toàn câu/ngữ cảnh thuế phí của nguồn. Không tự alias giá thành mọi mẫu số.
Giá bằng chữ xuống dòng cần giữ continuation; một lần match regex đầu dòng chưa
chứng minh đã đọc đủ giá trị. Không dùng metadata dựng kịch bản làm output extraction.

## 3. Phần có sẵn trong mẫu gốc: lấy theo từng nguồn

Những phần sau được đọc từ nội dung gốc/đính kèm hiện có, không được viết thêm:

| Phần nguồn | P2 bàn giao | Module dùng |
|---|---|---|
| Chủ thể, đại diện, vai trò bên bán | Đoạn về đúng bên; giá trị/role nếu xác định được, cùng evidence | Scope; criterion thông tin các bên |
| Mô tả căn hộ, cách đo diện tích, sở hữu chung/riêng | Chunks, cấu trúc và fact rõ ràng nếu có | Retrieval và compliance |
| Giá, thuế/phí, lịch thanh toán | Chunks/bảng có header/điều kiện; số/đơn vị khi đọc được | Retrieval; P4 xác minh và tính numeric |
| Bảo trì | Khoản tiền/tỷ lệ/cơ sở/cách tách nếu nguồn nêu | P4 bind đúng criterion và denominator; không lấy mọi giá làm base |
| Bàn giao, hồ sơ kèm theo | Câu cam kết, thời điểm/điều kiện, tài liệu được dẫn chiếu | Compliance nội dung; không tự thành performance proof |
| Bảo hành | Câu nguồn; số/đơn vị nếu đúng duration; mốc/ngoại lệ dưới dạng text | P4 chuẩn hóa `warranty_months/unit/start` theo đúng target/rule |
| Hiệu lực, phạt, bồi thường, chấm dứt, tranh chấp | Chunks/điều kiện có nguồn, không tự kết luận legal validity | Retrieval/compliance/risk |
| Viện dẫn pháp luật | C03: raw, số hiệu/tên/Điều/Khoản có nêu, vị trí và ambiguity | Citation Validation C09; không dùng citations thay checklist C05 |

Inventory có candidate text về bảo hành trong 89/90 mẫu, diễn đạt numeric warranty
trong 79/90, hiệu lực hợp đồng trong 85/90, lịch thanh toán trong 85/90, bảo trì
trong 89/90; 86/90 có candidate số hiệu văn bản. **Đây là số match, không phải số
clause đã được thẩm định hoặc tỷ lệ extraction accuracy.** Các mẫu còn lại có thể
viết khác, dẫn chiếu hoặc thật sự không nêu; cần giữ trạng thái phù hợp theo nguồn.

P2 không cần tạo mọi numeric field cho mọi criterion. Có thể bàn giao raw clause
và source candidate để P4 xác minh. `warranty_start`, numeric target, điều kiện
pháp lý và denominator review là phần P4, không suy từ sự có mặt của một số.

## 4. Những gì không được coi là sẵn có chỉ vì file mang nhãn DAY_DU

- NOXH/thương mại, loại giao dịch, tình trạng tài sản, vốn nước ngoài, mẫu/giao kết
  điện tử/trọng tài: chỉ gán giá trị khi có căn cứ phù hợp. Có 5/90 tiêu đề NOXH
  trực tiếp; các mẫu khác không được tự đổi thành `la_nha_o_xa_hoi=false`.
- Một câu điều kiện “trường hợp bên bán có vốn nước ngoài…” không xác nhận vốn
  của bên bán đang xét. Nhắc Tòa án/Trọng tài trong bảo mật chưa là chọn trọng tài.
- Ngày ký không thay ngày bắt đầu dùng mẫu, thỏa thuận đặt cọc, thu tiền thực tế
  hoặc bàn giao thực tế. Mẫu biên bản còn trống không là chứng cứ sự kiện đã xảy ra.
- Ngày của luật, số điều, watermark và dấu ba chấm không được biến thành facts
  của giao dịch. Không lấy ngày 25 tháng 11 làm thời hạn 25 tháng bảo hành.
- Không yêu cầu đưa `APPLICABLE`, `SATISFIED`, `human_verified`, `facts_verified`
  hoặc đáp án criterion vào PDF. P2 không sinh C07/C08/C10/C11.

Các field C02 ngoài tập quan sát chung vẫn được giữ trong contract để dùng khi
nguồn mới hoặc reviewed context được phép cung cấp. Không xóa chúng chỉ vì
corpus này không bảo đảm có giá trị; không giả lập chúng trong đường đọc PDF thật.

## 5. Quy tắc tiêu thụ và xử lý thiếu

| Module | Dùng nguồn gì? | Không được đòi producer làm gì? |
|---|---|---|
| Documents | C01 + bytes; đưa C02/chunks/C03 có nguồn | Không JOIN expected để tạo output PDF thật |
| Scope/Temporal | C02 có nguồn + snapshot knowledge | Không đòi boolean/ngày luôn known; thiếu giữ UNKNOWN với lý do đúng |
| Retrieval | C05 + chunks toàn tài liệu/nguồn hiện có | Không phụ thuộc mọi clause đã có scalar fact; vẫn tìm được text |
| Compliance | C05/C06 + rules + facts/evidence | Không coi keyword hoặc output LLM là verification; semantic clause không nhất thiết phải là profile field |
| Risk/Recommendation | C07/C08/C09 và provenance | Không yêu cầu Documents tạo nhãn rủi ro/khuyến nghị làm đầu vào |
| Report/UI | Profile và output cùng run | Không tái dùng seed để lấp field/đổi kết luận của run thật |

Không tìm thấy keyword/top-K không đủ kết luận nội dung vắng. MISSING chỉ khi
policy absence/coverage đạt; thiếu chứng từ thực hiện hoặc thiếu dữ kiện chọn
pháp luật không tự là vi phạm. FULL90 có thể vẫn UNKNOWN/INSUFFICIENT ở những
nhánh yêu cầu dữ kiện mà hợp đồng không nêu; đây phải là giới hạn có lý do, không
phải một việc điền thêm nội dung vào tài liệu.

## 6. Công việc và điều kiện bàn giao

P1 pin nguồn/split và inventory. P2 đọc đúng 19 trường sẵn có, chuẩn hóa CORE,
giữ các phần TARGETED trong text và trích conditional facts/citations có nguồn.
P3 dùng uncertainty đúng nghĩa. P4 chốt mapping/rule/verification cho criterion.
P5 truyền/lưu đầy đủ C02/chunks/C03, diagnostics và lineage.

Nghiệm thu P2 trên DEV/VAL phải đối chiếu nguồn độc lập: đọc được CORE đã có,
giữ unknown của biến thể thiếu, giữ hai giá của conflict, không lấy ngày luật
thành numeric fact, không suy sự kiện từ mẫu biểu. Tập FULL90 gồm 60 DEV, 15 VAL,
15 TEST; per-file inventory toàn bộ dành evaluator. Không dùng bảng này làm
gold labels pháp lý hoặc thay expected đã review độc lập.

Riêng đặc tả này không implement extractor hoặc thêm nội dung PDF. Release dữ liệu
tiếp theo đã cập nhật workbook/runtime và manifest, xem
[TEAM_BASELINE_20261107](../guides/dataset_team_baseline_20261107.md). Inventory nguồn
và yêu cầu không suy diễn dữ kiện thiếu vẫn được giữ.
