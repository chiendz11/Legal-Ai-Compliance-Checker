# Chấm lại E2E Gold từ nguồn — 14/11/2026

**Cập nhật mới:** xem [Gold Master thống nhất](gold_master_20261114.md).
Master 15/11 R4 hiện có **48/360 ca** đã chấm, **312 ca chờ chấm**; xem tài liệu Master
để tra các case, số liệu từng lớp và bản xuất hiện hành.
Master hợp nhất các lớp đáp án bằng SQLite/JSON và giữ nguyên phạm vi Scoped.
Các số liệu và gói 20 ca bên dưới là checkpoint r4 trước đợt bổ sung này;
không phải tiến độ mới nhất. `full_e2e_gold_ready` vẫn là `false`.

Đã chấm trực tiếp **20/360 ca**: HD360_001–004, 225–228, 277–280,
321–324 và 349–352 theo phạm vi bên dưới; **340 ca còn PENDING_ADJUDICATION**.
Lần bổ sung này hoàn tất thêm 16 ca, chưa hoàn thành yêu cầu chấm nốt 356 ca. `full_e2e_gold_ready=false`. Đợt này không gọi API LLM,
không chạy Qwen và không lấy nhãn từ output pipeline. Chưa hoàn thành yêu cầu
Gold toàn bộ 360 ca; không đổi tên bộ một phần thành bộ đầy đủ.

## Vì sao phải dựng lại?

Builder cũ lấy C05/C07/C08 từ `reference_cache.sqlite`, tự sửa trạng thái C05 theo
việc có C07, dùng lại nhãn C07 rồi gắn GOLD và tạo receipt ADJUDICATED bằng chuỗi.
Một quote có thật nhưng sai vai trò vẫn vượt kiểm tra kỹ thuật. C03 trích xuất
cũng bị dùng như đáp án C09. Các đáp án đó không dùng làm chuẩn độc lập để chấm
chính pipeline. Bản cũ được đưa ra khỏi đường đọc mặc định và lưu nguyên để truy vết.

## Nguồn và phạm vi đã khóa

- Nguồn PDF: `PDF360_DRAFT_GTC_V4_R2_20261110`; không sửa nội dung PDF.
- Knowledge: `V750_KNOWLEDGE_OWNER_APPROVED_20261110`.
- SHA-256 canonical JSON:
  `4ab2d7ea296ea908e25c09fcb6d5f073f1ebe1917678b36390f803b1c725804a`.
- 323 families, 357 versions, 479 criteria; chọn checklist theo C05 từng ca.
- Assessment context C01 công khai; chế độ `DRAFT_REVIEW`.
- Ghi nhận `AI_SOURCE_ADJUDICATED`, `human_legal_signoff=false`. Chủ dự án chấp
  nhận dùng AI biên soạn; không ghi chuyên gia là người thật đã ký/thẩm định.

Base HD360_001 đã được đọc toàn văn text theo 16 phần, 79 trang. Đã đọc toàn bộ
khác biệt văn bản của ba biến thể; không suy kết quả từ tên baseline/missing/
adverse/conflict. Đã xem ảnh trang PDF 29 và 33, xác nhận phụ lục bản vẽ không có
bản vẽ và bảng mô tả vật liệu để trống. Hồ sơ đọc ghi rõ full-text + targeted
visual checks; không khẳng định đã có hai chuyên gia độc lập hoặc kiểm tra mọi ảnh.

Đây là Gold theo catalog và phạm vi đánh giá dự thảo đã khóa, không chứng minh
giao dịch đã ký, đã thu tiền, đủ giấy phép, đã nghiệm thu, hoặc bao phủ mọi nghĩa
vụ pháp luật ngoài catalog.

## Kết quả đã chấm

| Lớp | Khối lượng | Cách chấm |
| --- | ---: | --- |
| Facts | 1.564 records | Đọc thân/phụ lục, tách vai trò, giữ nguồn, null, chuyển tiếp và xung đột |
| C05 | 6.460 dòng | Đủ 323 families/ca; scope từ facts, ngày đúng loại và khoảng hiệu lực |
| C07 | 2.674 dòng | 1.364 được xét: 1.056 SATISFIED, 29 VIOLATED, 84 MISSING, 195 UNKNOWN; 690 ngoài phạm vi dự thảo, 101 không phát sinh, 519 chưa phân giải scope |
| C09 | 418 occurrences | 265 VALID, 141 UNKNOWN, 12 INVALID; tách identity, temporal, domain và nguồn |
| C08 | 2.118 dòng | Tổng hợp độc lập theo findings và disposition đã chốt |
| C10/C11 | Có artifact theo từng ca | Chiếu rules/catalog/template đã khóa từ nhãn đã chấm, giữ provenance |
| Review/report | Có assertion theo từng ca | Review ban đầu PENDING, report DRAFT; không tạo human approval |

HD360_002 không có ngày giao kết và C01 không khai mốc thay thế đúng loại; 300
families giữ UNKNOWN, 23 không áp dụng theo scope. Chưa chọn được version nên
không tạo giả checklist C07. C13 phải hiển thị khoảng trống này; không biến nó
thành một ca tuân thủ vì có 0 criterion vi phạm.

### Các nhóm nguồn đã bổ sung

| Nhóm | Đã đọc | Kết quả nguồn đáng chú ý |
| --- | --- | --- |
| 225–228 | 27 trang baseline và toàn bộ khác biệt ba biến thể | Mốc 07/05/2024 nhưng viện dẫn Luật KDBĐS 2023 chưa có hiệu lực; thiếu kỳ hạn tài khoản bảo trì, danh mục phần chung và ngày hiệu lực; dẫn chiếu nhầm định nghĩa diện tích |
| 277–280 | 7 trang baseline và toàn bộ khác biệt ba biến thể | Tên công ty/cá nhân không đủ chứng minh tư cách giao dịch kinh doanh–tiêu dùng; thiếu dữ kiện mục đích và vai trò phải giữ scope chưa rõ |
| 321–324 | 21 trang baseline và toàn bộ khác biệt ba biến thể | Danh mục sở hữu chung và thông số phạt còn trống; đợt 5% còn nhánh yêu cầu trả sớm khi tự xin giấy; có điều khoản đơn phương thay đổi; ngoại lệ bảo hành cần phân giải phạm vi |
| 349–352 | 30 trang baseline và toàn bộ khác biệt ba biến thể | NOXH; xung đột tên/vị trí dự án, hiệu lực gắn cọc dù phụ lục không cọc, số bảo trì trên giá gồm VAT trái cơ sở trước VAT được ghi |

Đã đọc đủ 19 Điều của Mẫu số 01 NĐ02/2022, đối chiếu từng khoản với nhóm
225–228, không chấm đạt chỉ vì có tiêu đề. Kiểm ảnh chính văn trang PDF 22–24,
33–34 xác nhận điều kiện bảo lãnh và ngoại lệ bảo hành. Điều khoản “bên thứ ba”
cũng có trong mẫu pháp quy, vì vậy không tự kết luận vi phạm chỉ bằng cụm từ đó;
đáp án giữ cần phân giải phạm vi lỗi thuộc trách nhiệm bên bán với lỗi bên ngoài.
Nguồn: [Nghị định 02/2022, PDF chính thức](https://datafiles.chinhphu.vn/cpp/files/vbpq/2022/01/02.signed.pdf).

Bộ biên soạn mới dùng C01 JSON công khai thay vì đọc cache. Mã chế độ giao dịch
được kiểm đúng vocabulary của scope (`KINH_DOANH_BDS`, `BAN_LAI_CA_NHAN`,
`LUAT_NHA_O`, `NOXH`); mã ngoài bộ không được biến âm thầm thành NO_MATCH.
Các ca sau 01/08/2024 phải được chấm chuyển tiếp riêng trước khi dùng oracle này;
chưa có đáp án thì vẫn PENDING, không dùng lỗi thiếu implementation làm UNKNOWN.

Từng nhóm có source-review receipt, rationale, evidence riêng theo checksum PDF,
10 artifacts và group gate. 20 ca hiện gồm **16 DEV + 4 VALIDATION**; chưa chấm
ca TEST trong đợt này. Không suy nhãn pháp lý từ tên baseline/missing/adverse/conflict.
Các nhóm mới được ưu tiên theo khả năng đọc/đối chiếu nguồn, không phải mẫu ngẫu nhiên
đại diện toàn bộ corpus. Metric trên phần này không được suy thành metric 360 ca.

Phạm vi NOXH 2015–2024 của catalog đóng băng chưa có checklist chuyên biệt đầy đủ
cho NĐ100/2015 và TT20/2016. Đáp án ghi rõ gap đó; không tự áp toàn bộ checklist
nhà thương mại hoặc kết luận NOXH được miễn nghĩa vụ. Định danh hai văn bản này
được đối chiếu riêng bằng [Cổng Chính phủ — NĐ100/2015](https://vanban.chinhphu.vn/?docid=182065&pageid=27160)
và [TT20/2016](https://vanban.chinhphu.vn/?docid=185869&pageid=27160),
không thay đổi hash knowledge đã khóa. Luật KDBĐS 2023 được đối chiếu
[nguồn ban hành chính thức](https://chinhphu.vn/?docid=209624&pageid=27160):
không có hiệu lực tại ngày kịch bản 07/05/2024, kể cả sau khi xét sửa đổi mốc năm 2024.

### Các quyết định quan trọng

- **DS436_01:** evidence là kiểm tra/đo diện tích/ký biên bản tại căn hộ, không
  dùng Fax/thư thông báo.
- **DS453_01/02:** lịch thanh toán xây dựng và 5% chờ Giấy chứng nhận tự nó chưa
  chứng minh mua chịu theo Điều 453. Đọc toàn văn không thấy thời hạn tín dụng
  sau giao nhà độc lập; giữ NOT_TRIGGERED, không coi bảo lưu sở hữu tự là vi phạm.
- **Địa chỉ các bên:** HYC039_02 dùng đúng hai dòng địa chỉ, không dùng tên bên bán.
- **Bảo hành:** HD360_003 dùng 36 tháng tại phụ lục có câu thay thế; chấm dưới
  ngưỡng 60 tháng, không lấy 60 tháng cũ trong thân hợp đồng để bỏ qua vi phạm.
- **Giá:** HD360_004 giữ hai giá đang cùng áp dụng; UNKNOWN đúng vì xung đột nguồn,
  không chọn một giá để làm metric đẹp.
- **Bảo trì:** giá gross gồm VAT, điều khoản tính bảo trì trên giá chưa VAT và số
  phụ lục chưa nhất quán; thiếu breakdown nên chưa tự tính VAT hoặc kết luận số đúng.
- **Chung/riêng theo thiết kế:** có danh mục nhưng không có bản thiết kế phê duyệt
  để đối chiếu; UNKNOWN có lý do nguồn, không phải chưa viết verifier.
- **Ngôn ngữ:** phát hiện dẫn chiếu nhầm khoản định nghĩa diện tích sử dụng/sàn.
- **Điều khoản người tiêu dùng:** chấm giới hạn nghĩa vụ bên bán ngoài hợp đồng
  và quyền đặt quy định khác của đơn vị quản lý theo Điều 16 Luật 59/2010.

Các quyết định nguồn luật được lưu cùng rationale và legal article IDs; tham khảo
[Luật BVQLNTD 59/2010](https://vanban.chinhphu.vn/?classid=1&docid=98755&orggroupid=1&pageid=27160),
[Luật Nhà ở 65/2014](https://datafiles.chinhphu.vn/cpp/files/vbpq/2014/12/65.signed.pdf),
[Luật KDBĐS 66/2014](https://datafiles.chinhphu.vn/cpp/files/vbpq/2014/12/66.signed.pdf),
[Bộ luật Dân sự 91/2015](https://datafiles.chinhphu.vn/cpp/files/vbpq/2016/01/91_.pdf).
Điểm nộp bảo trì trước bàn giao được đối chiếu bản gốc
[Nghị định 99/2015, Điều 36 khoản 2](https://scov.gov.vn/van-ban/van-ban-phap-quy-phap-luat/nghi-dinh-99-2015-nd-cp-cua-chinh-phu-quy-dinh-chi-tiet-va-huong-dan-thi-hanh-mot-so-dieu-cua-luat-nha-o.html),
không lấy bản sửa đổi năm 2021 thay chế độ của kịch bản 2017.
Đây là kết luận tham chiếu của AI cho đồ án, có thể được phản biện bằng nguồn;
không dùng cờ owner-approved để bỏ qua ngoại lệ hay thiếu căn cứ.

## Relevance và viện dẫn được giới hạn thế nào?

Relevance pool chứa các block nguồn đã được tác giả chọn/chấm, cùng hard negatives
cụ thể cho DS436 và context controls cho GTC. Ngoài pool là UNJUDGED. Nó độc lập
với chunk ID/ranking production, nhưng **chưa là relevance đầy đủ mọi cặp block ×
criterion**. Chỉ công bố recall trên pool, không gọi là recall toàn văn.

Citation inventory gồm tên văn bản pháp luật rõ ràng, số hiệu và một viện dẫn
đại từ chưa phân giải. Dẫn chiếu Điều/Khoản/phụ lục nội bộ không tự thành statute.
Quy chế quản lý chung cư chỉ có tên nhưng thiếu số/năm không bị tự gán TT02/2016.
Với HD360_002, thiếu mốc nên temporal UNKNOWN dù định danh được một số văn bản.
VALID theo mốc kịch bản năm 2017 không có nghĩa văn bản còn hiệu lực hiện nay.

## Code đã sửa để tránh lặp lỗi

1. `devtools/build_complete_gold.py` chỉ nhận cases và artifacts đã biên soạn,
   kiểm source/knowledge/quote/ownership rồi đóng gói. Không còn đọc reference
   cache hay tự chọn finding. Chặn ghi đè release và chặn thu nhỏ denominator.
2. `gold_answers.py` yêu cầu artifact có nội dung, hash và pins cho từng lớp;
   receipt bằng chuỗi không đủ. So projection với artifact, kiểm quote trong
   citation/pool, chặn dùng lý do lỗi xử lý làm Gold và phân biệt C03 với C09.
3. Evaluator mặc định đọc `GOLD_DATASET_PATH=data/private/gold`, không đọc lại
   data cũ trong module. Không tính excluded/pending vào metric; thiếu prediction
   là NO_PREDICTION, không tự được điểm UNKNOWN; C05 join theo requirement_id và
   so cả applicability/version. Quote overlap vẫn chỉ là phép so quote đơn giản,
   không phải thước đo chứng minh grounding pháp lý hay Evidence Recall@K đầy đủ.
4. Dataset sinh, kể cả đáp án TEST, nằm ngoài Git. Scoped Gold trước giữ nguyên
   phạm vi đã công bố, không tự nâng thành E2E.

## Dùng dữ liệu mới

Đường đọc mặc định trong repo:

```text
data/private/gold -> gold_reauthored_20261114_r4/
  cases/                     # chỉ 20 ca đã chấm
  artifacts/CA360_xxx/        # 10 file/lớp thực, có hash
  SOURCE_INDEX.json          # vẫn đủ 360 ca
  GOLD_COVERAGE.json
  FULL_RELEASE_GATE.json     # global false; 340 ca còn chờ
  PENDING_ADJUDICATION.json
```

Hồ sơ biên soạn và gói xuất nằm tại:
`/home/chienqt/Downloads/legal_compliance_gold_reauthored_20261114/`.
Không seed bộ đáp án này đè runtime. Không cần đổi PDF hay DB ứng dụng để đọc Gold.
Benchmark inference toàn bộ DEV/VALIDATION/TEST **chưa được chạy trong đợt này**.

Đã chạy 34 unit tests về admission/đóng gói/chấm điểm, Ruff lint và format đều
pass. Đã kiểm checksum 360 PDF, quote/offset/ownership của 20 ca biên soạn,
artifact bindings và đọc lại workbook xuất. Các phép kiểm kỹ thuật này không
thay việc đọc/chấm pháp lý 340 ca còn lại.

Gói checkpoint hiện tại nằm trong thư mục biên soạn:

- `GOLD_REAUTHORED_MASTER_20_OF_360.xlsx`: 20 đáp án đã chấm và mục lục đủ 360 ca.
- `GOLD_REAUTHORED_DEV_VALIDATION_20_OF_300.xlsx`: 20 đáp án DEV/VALIDATION;
  còn 280 ca của tập nhóm chưa chấm.
- `PARTIAL_E2E_GOLD_REAUTHORED_20261114_20_OF_360.zip`: JSON, artifacts,
  workbook đọc, 20 PDF tương ứng, source text và hồ sơ biên soạn.
- `AUTHORING_CHECKPOINT_20.json`: case IDs, counts, nguồn, giới hạn và hash scripts.

Đây là workbook đáp án riêng để đọc/đối chiếu, **không phải workbook seed runtime**;
không ghi đè dataset TEAM hoặc DB đang phát triển. Gói 4 ca trước vẫn được giữ lại.

Lệnh đóng gói lại sau khi bổ sung thêm đáp án đã chấm (dùng output mới):

```bash
python -m devtools.build_complete_gold \
  --curated-root /path/to/curated_answers \
  --sources-root /path/to/source_text \
  --pdf-root /path/to/sources/pdf \
  --snapshot /path/to/knowledge_snapshot.json \
  --source-index /path/to/SOURCE_INDEX.json \
  --output data/private/gold_next
```

Phần chưa xong là chấm 340 ca còn lại từ nguồn theo cùng hồ sơ. Có đủ PDFs,
knowledge và file JSON không tự đóng công việc đó. Chỉ công bố full E2E Gold
360 khi toàn bộ ca đã có annotation và artifacts đạt kiểm tra, đồng thời đã
thực hiện rà nguồn tương ứng; kỹ thuật PASS không tự chứng minh pháp lý đúng.
