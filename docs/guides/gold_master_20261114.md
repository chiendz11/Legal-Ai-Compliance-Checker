# Gold Master thống nhất — 16/11/2026, R12

Một nguồn đáp án nhiều lớp dùng cùng PDF, knowledge và policy đã khóa. Hiện có
**220/360 ca đã biên soạn trong phạm vi công bố, 140 ca PENDING_ADJUDICATION**.
`full_e2e_gold_ready=false`: yêu cầu hoàn tất toàn bộ 360 ca chưa đạt.
Không dùng tên bản xuất hoặc số lượng dòng làm bằng chứng đã thẩm định toàn bộ.

Phân chia đã chấm: **100 DEV + 60 VALIDATION + 60 TEST**. Gói TEAM có
**160/300 ca đã chấm; 140 ca DEV còn chờ**, thuộc 35 nhóm nguồn. Đáp án TEST chỉ
nằm trong Master dành cho evaluator. Gói TEST INPUTS vẫn chỉ có 60 PDF, C01 và
snapshot chung; không có đáp án hoặc source text đã trích xuất. Chưa chạy blind
benchmark và chưa công bố accuracy/F1.

## R12 đã thay đổi gì?

R12 tiếp nối 204 ca của R11 và thêm **16 ca: 133–136, 141–144, 285–288, 305–308**.
Đã biên soạn 55/90 nhóm. Việc biên soạn ghi `AI_SOURCE_ADJUDICATED`,
`human_legal_signoff=false`, `production_outputs_used=false`. Không gọi API AI
hoặc model local, không lấy output pipeline để đổi nhãn thành Gold.

- **133–136, Asiana Paramount, mốc 17/5/2023:** đối chiếu từng phần với 19 Điều
  Mẫu số 01/NĐ02/2022. Số 4/5/6 cạnh trường đất và 12 cạnh thời gian chậm là
  ký hiệu chú thích, đã xem ảnh; không gán thành giá trị dữ kiện. Giữ việc mã hợp
  đồng bị điền nhầm vào trường đăng ký doanh nghiệp, hai tài khoản của cùng bên
  bán khác nhau và phạm vi giá có/không gộp bảo trì chưa thống nhất. Điều khoản
  đòi 95% trước nhận nhà và 100% trước cấp hồ sơ GCN nằm ngoài bảng lịch mới,
  nên không tự bị câu thay lịch xóa bỏ. Kỳ hạn tài khoản ghi “không kỳ hạn”
  được phân biệt với kỳ hạn còn trống.
- **141–144, PAVNC/P.A Tower, mốc 11/3/2024:** giữ hai dự án/địa điểm Đà Nẵng
  và Hà Nội, hai bộ thông tin đất và phạm vi giá/phí mâu thuẫn. Địa chỉ dự án
  khác trụ sở pháp nhân, nên không tự dựng xung đột địa chỉ bên bán từ hai vai trò.
  Bản vẽ/vật liệu chỉ có tiêu đề; kỳ hạn tiền gửi chưa được điền. Đối chiếu
  Mẫu số 01 theo nội dung, không chỉ tên/số Điều. Các chú thích khuyến cáo của
  cơ quan cạnh tranh không tự trở thành trần pháp luật bắt buộc.
- **285–288, Thuận Phát, mốc 18/10/2020:** phân biệt đất toàn dự án, sàn tòa nhà
  và sàn căn hộ; giữ xung đột thật về đất, địa chỉ, tài khoản. Nguồn ghi sai ngày
  ban hành TT06/2019; không sửa âm thầm PDF để viện dẫn thành hợp lệ. Bản286
  bỏ các ngày tương ứng; C05 giữ chưa phân giải và không tự tạo C07 khi chưa có
  version để chấm. Số dòng C07 bằng 0 trong ca đó không phải annotation bỏ dở.
- **305–308, Tân Phú, mốc 13/3/2019:** địa chỉ bên bán mâu thuẫn nhưng không
  suy trụ sở công ty là địa chỉ dự án. TT06/2019 còn ở tương lai tại ngày giả định.
  Đối chiếu điều kiện loại bảo hành, khoản cuối trước GCN và quyền tự sửa có nguồn;
  không dùng một câu sửa chữa để xóa điều kiện bất lợi khác vẫn còn trong văn bản.
- **Bốn ca 157–160:** sửa duy nhất số khoản trong lý do của `TC_PV_HYC037_02`:
  giới hạn khoản cuối thuộc **Điều57 khoản1**, không phải khoản2 Luật66/2014.
  Findings, dispositions, facts, C05/C08 và evidence giữ nguyên; receipts được tính
  lại theo reason mới. Bản R11 đã xuất giữ nguyên byte; R12 có bảng erratum riêng.
  200 ca ROOT khác đã có ở R11 giữ nguyên SHA-256.

Nguồn đã đọc gồm toàn văn chuẩn/delta từng biến thể và ảnh khi cần kiểm bố cục.
Riêng nhóm133: toàn bộ block có bản đồ đọc; các đoạn trùng nguyên nội dung sau
chuẩn hóa khoảng trắng được đối chiếu nguồn141 đã đọc trong cùng đợt, toàn bộ
phần không trùng được đọc riêng. Nhãn pháp lý không được tự chuyển theo tỷ lệ
đoạn trùng. Curator của từng nhóm ghi facts, quyết định và refs nguồn riêng.

Công cụ biên soạn bổ sung `context_refs` cho viện dẫn qua nhiều block: ví dụ số
Nghị định bị tách trước “CP” vẫn giữ cả block kề làm ngữ cảnh. Quote, offset và
SHA-256 vẫn lấy đúng PDF của từng ca; không sửa cách chia chunk của ứng dụng.

Nguồn pháp luật bổ sung được ghi kèm phạm vi đọc thực tế trong
`authoring/legal_sources/R12_PRIMARY_SOURCE_REGISTER.json`. Ví dụ, tra danh sách
công bố dự án của Quảng Ninh mới xác nhận được định danh một quyết định; chưa có
bản gốc/lịch sử thì hiệu lực và binding dự án vẫn chưa được xác nhận. VBHN được
phân biệt với văn bản gốc tạo hiệu lực; không coi ngày hợp nhất là ngày hiệu lực mới.

## Các lớp của cùng Master

| Lớp | Số dòng | Phạm vi được chấm |
| --- | ---: | --- |
| APPENDIX_LITERALS | 12.960 | 36 trường/ca trong chính phụ lục synthetic |
| NUMBERED_MENTIONS / CATALOG_IDENTITY | 4.569 / 4.569 | Số hiệu/membership catalog đã khóa, chưa thay C09 |
| FACTS | 17.128 | Hồ sơ toàn văn của 220 ca; giữ vai trò và mâu thuẫn |
| SCOPE_TEMPORAL — C05 | 71.060 | 323 families × 220; scope/date/version trước checklist |
| CRITERIA — C07 | 34.021 | 18.149 ASSESSED; disposition giữ riêng |
| CITATION_OCCURRENCES — C09 | 7.726 | Từng lần xuất hiện, định danh/thời gian/lĩnh vực |
| RETRIEVAL_JUDGED_POOL | 73.519 | Pool witness/control hữu hạn; ngoài pool UNJUDGED |
| AGGREGATION — C08 | 25.486 | Tổng hợp theo policy từ đáp án biên soạn |
| RISKS / RECOMMENDATION_ASSERTIONS | 13.340 / 13.340 | Giữ nguồn và hành động cần có, không ép câu chữ model |
| REVIEW_POLICY / REPORT_ASSERTIONS | 220 / 220 | Điều kiện review/publish và assertion report |

18.149 criterion ASSESSED gồm **12.562 SATISFIED, 1.239 VIOLATED, 424 MISSING,
3.924 UNKNOWN có lý do nguồn**. Giữ riêng 9.997 ngoài phạm vi, 971 không phát sinh
điều kiện và 4.904 chưa phân giải scope. Không gộp những disposition này thành
UNKNOWN pháp lý khi tính accuracy. 140 ca chưa chấm tương ứng 1.400 đơn vị lớp
còn chờ; không có nhãn full-case để chấm chúng.

420 số hiệu từng chờ binding đã có đáp án `NO_MATCH_IN_PINNED_CATALOG` trong
phạm vi catalog cố định. Điều đó không chứng minh văn bản ngoài đời không tồn tại
và không tự chuyển thành INVALID.

## Đường dẫn và kiểm tra bản xuất

```text
data/private/gold -> gold_master_20261116_r12/  # chỉ chọn sau khi kiểm tra xuất PASS
  gold_master.sqlite          # nguồn đáp án query được
  GOLD_MASTER.xlsx            # bản dễ đọc, không thay payload dài của SQLite/JSONL
  answers.jsonl
  cases/                      # 220 ca biên soạn
  artifacts/                  # 10 lớp/ca, receipts và hashes
  imports/                    # Scoped và proposal giữ đúng phạm vi ban đầu
  sources/pdf/                # 360 PDF giữ nguyên checksum
  sources/text/               # source blocks của reader độc lập
  public_inputs/              # C01 công khai
  knowledge_snapshot.json
  POLICY_SNAPSHOT.json
  SOURCE_INDEX.json
  GOLD_COVERAGE.json
  PENDING_ADJUDICATION.json
  FULL_RELEASE_GATE.json      # full_e2e_gold_ready=false
  INCREMENTAL_VALIDATION.json # lineage so với R11, gồm bốn errata
  authoring/                  # curators, biên bản đọc, group gates, source guards
```

Thư mục xuất R12:
`/home/chienqt/Downloads/legal_compliance_GOLD_MASTER_20261116_R12/`.
Giữ R11/R10 để truy vết. `FINAL_VERIFICATION.json` là kết quả cuối của kiểm tra
hash/CRC/SQLite/tách split, không phải chứng thư thẩm định của chuyên gia con người.
Source guards kiểm lỗi đã nhận diện, không tự chứng minh toàn bộ chất lượng pháp lý.

Master chứa đáp án TEST chỉ phát cho evaluator. Gói TEAM đã loại TEST vật lý trong
SQLite/workbook và ZIP; view lọc TEST không thay cách ly dữ liệu. **Không seed DB
Gold đè PostgreSQL runtime**, không tự đổi PDF/knowledge/workbook seed hoặc
triển khai ứng dụng trong đợt biên soạn này.

## Khóa của một đáp án và ý nghĩa trạng thái

Khóa duy nhất: `case_id + layer + question_scope + target_id`; case khóa thêm
SHA-256 PDF, knowledge và policy. Hai đáp án cho cùng câu hỏi trong một revision
bị từ chối, không ghi đè âm thầm.

Ví dụ cùng câu hỏi về diện tích nhưng hai phạm vi khác nhau:

- Phụ lục ghi 75,35 m²: đáp án cho việc đọc giá trị **trong phụ lục**.
- Thân và phụ lục mô tả nhất quán đúng căn hộ chưa: câu hỏi **toàn bộ tài liệu**.

Đáp án đầu tiên không tự giải quyết câu hỏi thứ hai. Tương tự, không thấy dữ kiện
trong phụ lục chưa chứng minh toàn bộ PDF thiếu dữ kiện; thấy số hiệu chưa chứng
minh văn bản đúng thời điểm/lĩnh vực.

`annotation_status=PENDING_ADJUDICATION` là chưa chấm, không được tính điểm.
Một đáp án đã chấm có thể có `finding=UNKNOWN` khi nguồn thực sự thiếu hoặc mâu
thuẫn; lý do đó phải được ghi cụ thể. `OUTSIDE_REVIEW_SCOPE`, `NOT_TRIGGERED`,
`SCOPE_UNRESOLVED` là disposition riêng, không gộp vào accuracy của UNKNOWN pháp lý.

## Tra cứu bằng SQL

Mở `gold_master.sqlite` bằng DB Browser for SQLite, DBeaver hoặc Python sqlite3.
Đây là DB đáp án của evaluator, tách khỏi PostgreSQL runtime.

```sql
-- Việc thực sự còn chờ: không phải danh sách lỗi inference.
SELECT case_id, layer, reason
FROM pending_work
ORDER BY case_id, layer;

-- Chỉ các nhãn criterion thực sự được đánh giá, không trộn mục ngoài phạm vi.
SELECT case_id, target_id,
       json_extract(payload_json, '$.finding') AS finding,
       json_extract(payload_json, '$.reason') AS reason
FROM criterion_finding_answers
WHERE case_id = 'CA360_337';

-- Đi ngược từ đáp án đến đúng quote và vị trí PDF.
SELECT a.case_id, a.target_id, e.page, e.source_ref,
       e.start_offset, e.end_offset, e.quote
FROM answers a JOIN evidence e USING(answer_id)
WHERE a.case_id = 'CA360_337'
  AND a.layer = 'CRITERIA'
  AND a.target_id = 'TC_PV_DS436_01';
```

Không dùng `SELECT * FROM answers` rồi chấm toàn bộ bằng một metric.
Mỗi lớp có câu hỏi, phạm vi và điều kiện tính điểm riêng.

Evidence dùng `source_ref` của reader độc lập, trang và offset trong block nguồn.
Khi module Documents chia chunk khác, cần ánh xạ kết quả về cùng trang/quote/vị trí
nguồn trước khi chấm Retrieval; không so bằng việc `chunk_id` có giống đáp án hay
không. Recall@K chỉ có ý nghĩa trong pool đã công bố; một witness chưa phải toàn
bộ các đoạn có thể liên quan trong tài liệu.

## Đã bổ sung gì ở CA360_337–340?

Đọc toàn bộ 29 trang baseline trong sáu phần text, mọi delta của ba biến thể và
xem ảnh trang 6, 25, 26. Đối chiếu cả nội dung được giữ ở thân và phụ lục thay thế.

- Phương thức bàn giao: lấy bước kiểm tra, đo và lập biên bản tại Điều 8;
  dùng Fax của Điều 16 làm control không liên quan, tránh lặp lại lỗi DS436.
- Bảo lưu sở hữu: phân biệt thanh toán theo tiến độ/giữ 5% chờ GCN với cấp tín dụng
  trả chậm sau nhận tài sản; không lấy một câu bảo lưu làm kết luận vi phạm DS453.
- Bảo hành: bản339 có câu thay thời hạn của thân bằng 36 tháng; chấm riêng yêu cầu
  tối thiểu, không lấy 60 tháng của thân cũ để bỏ qua thay đổi.
- Bản340: giữ hai giá cùng vai trò, không tự ưu tiên số đầu.
- Bản338: thiếu mã/tầng/diện tích và các phụ lục dẫn chiếu chưa được cung cấp;
  không giả rằng các tài liệu chưa nhận cũng không có thông tin.
- Nguồn baseline vẫn có vị trí căn hộ TP.HCM nhưng đất phụ lục Hà Nội, phạm vi VAT
  chưa rõ, các ngoại lệ bảo hành cần làm rõ. Những UNKNOWN này có câu chữ cụ thể
  trong nguồn, không lấy tên baseline làm chứng nhận tuân thủ.

Nguồn đối chiếu gồm KB đã khóa, [Bộ luật Dân sự 91/2015](https://vanban.chinhphu.vn/?docid=183188&pageid=27160)
và [Luật Bảo vệ quyền lợi người tiêu dùng 59/2010](https://vanban.chinhphu.vn/?classid=1&docid=98755&orggroupid=1&pageid=27160),
cùng nguồn Luật Nhà ở/NĐ99 đã lưu trong hồ sơ biên soạn. Không cập nhật âm thầm
knowledge để làm PDF được điểm tốt hơn.

## Revision 14/11 R4 bổ sung gì?

Đọc thêm ba nhóm nguồn và các delta của cả bốn biến thể, không sao chép kết quả
của pipeline hoặc chuyển mọi ô UNKNOWN sang SATISFIED:

- Đối chiếu ngày bàn giao, tên người mua, địa chỉ và phạm vi giá ở thân/phụ lục.
  Ví dụ nhóm197 có tháng12/2018 ở thân và30/12/2020 ở phụ lục nhưng không có
  câu thay thế điều khoản giao; giữ xung đột có nguồn thay vì tự chọn ngày mới.
- Phân biệt bảng vật liệu có thông số thực với bảng chỉ có khung trống. Nhóm313
  có bảng hoàn thiện chung/riêng còn trống, khác bảng vật liệu có thông số của197.
- Đối chiếu viện dẫn theo đúng ngày của kịch bản. Nhóm313 có thông tư đã ban hành
  nhưng chưa hiệu lực và thông tư chưa ban hành ở ngày19/7/2019; không lấy ngày
  đánh giá hiện tại để biến chúng thành căn cứ phù hợp.
- Bổ sung kiểm tra ràng buộc source/case/date cho chính sách chuyển tiếp sau
 1/8/2024 và phạm vi NOXH. Thiếu hồ sơ chuyển tiếp không tự được coi là dự án
  đã đủ điều kiện hoặc tự dùng mẫu thương mại cho mọi loại nhà.
- Hoàn tất420 đáp án âm về membership của catalog trong phạm vi đã nêu ở trên.

Nguồn mới gồm [Công báoTT10/2018](https://congbao.chinhphu.vn/van-ban/thong-tu-so-10-2018-tt-bxd-28110/25252.htm),
[TT01/2019, Điều2 tại trang54 Công báo](https://congbao.cdnchinhphu.vn/CongBaoCP/CongBao/2019/7/29304/27392-1-603-604.pdf),
[Luật43/2024](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/9/43-2024-qh15.pdf)
và văn bản nhà ở đã khóa trong hồ sơ biên soạn. Bản tải vàSHA-256 được giữ cùng
Master; không gọi dịch vụ gán nhãn bằng mô hình khác.

## Revision 15/11 R4 bổ sung gì?

Bổ sung hai nhóm 177–180 và 185–188. Đọc toàn bộ 31 và 29 trang tương ứng,
tất cả khác biệt của các biến thể, cùng ảnh và dữ liệu font tại các trang liên quan.
36 ca đã phát hành ở bản ngày 14/11 giữ nguyên byte. Bổ sung thêm bốn ca TEST
325–328 sau revision 15/11 R3; hồ sơ chấm chi tiết của TEST chỉ có trong Master
evaluator. PDF và snapshot knowledge không đổi.

- **177–180:** ngày giả định 26/7/2024 nằm giữa hai mốc hiệu lực. Luật tiêu dùng
  2023 đã áp dụng, nhưng Luật Nhà ở/KDBDS 2023 và NĐ95/96 chưa hiệu lực.
  C05 chọn nguồn từ scope/date, độc lập với những văn bản mới bị dẫn sớm trong PDF.
  Đối chiếu đủ 19 Điều của Mẫu 01/NĐ02/2022, gồm các mục cho phép thỏa thuận và
  các phụ lục phải có.
- **185–188:** ngày 4/8/2024 cần kiểm tra chuyển tiếp. Giấy đủ điều kiện bán trước
  1/8 chưa được cung cấp nên không tự gán False cho dữ kiện chuyển tiếp. Các nhánh
  catalog cần thông tin đó giữ chưa phân giải, kèm lý do từ nguồn. Thông tư 10/2015
  đã bị bãi bỏ được chấm STALE tại ngày của kịch bản 2024.
- Giữ những xung đột thật về địa chỉ, đại diện, đất/dự án, tài khoản, giá gồm/tách
  bảo trì và năm hoàn thành so với ngày giao. Hai giá trong bản conflict không bị
  tự chọn một giá vì khớp phép nhân. Bản missing chỉ bỏ đúng các trường của nó:
  186 vẫn có tỷ lệ bảo trì 2% trong một dòng mà literal parser không nhận nhãn.
- Thời hạn 36 tháng của 179/187 được đối chiếu mức tối thiểu 60 tháng cho chung cư
  mới. Tiêu chí hỏi có thời hạn/mốc bảo hành khác tiêu chí hỏi có đủ mức tối thiểu.
- Kiểm font 177: chú thích nội dung bảo trì là Times New Roman 9,96 pt, khác dòng
  watermark kiểm thử. Với 185 dùng font khác, chưa có phép so kích cỡ tương đương
  được khóa thì không suy đơn giản mọi chữ 10 pt đều vi phạm.
- Lưu/cấp bản sao, đăng ký/công khai và thời gian nghiên cứu là nghĩa vụ thực hiện
  cần đúng loại bằng chứng. Dự thảo không có câu lưu trữ không tự là MISSING điều
  khoản. Bổ sung kiểm tra từ chối loại nhãn này khi catalog ghi rõ nghĩa vụ ngoài
  văn bản, không bắt buộc có điều khoản và cấm dùng MISSING. Kiểm tra không loại
  máy móc tiêu chí về nội dung hợp đồng chỉ vì một cờ metadata phân loại thô.
- Rà lại vị trí evidence: bỏ watermark/số trang khỏi các witness nội dung; giữ số
  ngày/tháng/năm đã điền đúng vai trò. Thêm control cho số trang và thông báo Fax,
  tránh tính chúng là evidence của bản vẽ hoặc phương thức bàn giao căn hộ.

C07 dùng chấm finding có 3.585 mục ASSESSED: 2.616 SATISFIED, 96 VIOLATED,
114 MISSING, 759 UNKNOWN có nguyên nhân nguồn. 2.008 ngoài phạm vi, 239 không
phát sinh điều kiện và 1.132 chưa phân giải scope được giữ riêng. Không trộn tất
cả 6.964 dòng vào một accuracy.

Nguồn thời gian mới được kiểm từ [Thông tư 03/2021](https://congbao.chinhphu.vn/van-ban/thong-tu-so-03-2021-tt-bxd-33752/35834.htm),
[Thông tư 05/2024](https://moc.gov.vn/pl/pages/ChiTietVanBan.aspx?vID=420)
và [Quyết định 321/2024, dòng TT10/2015 ở trang 74 của PDF](https://congbao.cdnchinhphu.vn/CongBaoCP/VanBan/2024/4/41742/49828-1-2024575-576321-qd-bxd.pdf).
Hồ sơ nguồn và checksum được giữ ở `authoring/legal_sources` cùng Master.

Bản xuất nằm trong `/home/chienqt/Downloads/legal_compliance_GOLD_MASTER_20261115_R4/`:
Master 48/360 cho evaluator; TEAM 40/300 gồm DEV/VALIDATION; TEST INPUTS 60 ca
không chứa đáp án. Gói TEAM không có các bản ghi, file source hoặc code biên soạn
riêng của TEST.

47 test của công cụ Gold và Ruff đã qua. Kiểm tra này chứng minh các ràng buộc
kỹ thuật được kiểm, không thay một lượt thẩm định pháp lý độc lập của người thật.

## Kiểm tra và giới hạn benchmark

Builder `devtools/gold_master.py` kiểm pins của 360 PDF/source/index, source spans,
ownership, phạm vi literal, định danh với catalog, ranh giới split theo nhóm nguồn,
hash artifact và khóa đáp án duy nhất. File output phải là thư mục mới.

Các kiểm tra này chưa chứng minh mọi suy luận pháp lý đúng. Biên soạn được ghi
`AI_SOURCE_ADJUDICATED`, `human_legal_signoff=false`, không tạo tên/chữ ký chuyên
gia là người thật hoặc receipt duyệt của người khác.

Chưa chạy benchmark inference toàn bộ DEV/VALIDATION hoặc blind TEST trong đợt này.
Chỉ được báo metric cho target/pool đã chấm và ghi rõ mẫu số, không dùng 140 ca còn
chờ làm đáp án UNKNOWN. Chưa được công bố accuracy/F1 toàn bộ 360 ca hoặc Recall@K
toàn corpus dựa trên pool hữu hạn này.

Không seed đáp án Gold đè PostgreSQL runtime; không thay gói TEAM trên Drive hay
dataset manifest đang phục vụ DB của nhóm chỉ vì việc hợp nhất đáp án này.
Để hoàn tất Gold E2E, vẫn phải chấm 292 ca còn lại từ nguồn theo từng lớp, xử lý
chuyển tiếp 2024 ở những ca có liên quan, rồi phát hành revision mới sau kiểm tra.


## Revision 15/11 R6 — ba nhóm nguồn bổ sung

Đã đọc đầy đủ các nhóm 077–080 (35 trang baseline), 097–100 (36 trang),
237–240 (35 trang) và mọi thay đổi của từng biến thể. Có kiểm tra ảnh các trang
định danh, bảng vật liệu, phần sở hữu và phụ lục; không sửa PDF/knowledge.

- 077–080: tách số footnote khỏi tên pháp nhân sau khi đối chiếu ảnh; giữ mâu thuẫn
  mục đích ở/kinh doanh. Bản thiếu ngày không mượn ngày bàn giao để chọn luật.
  Bản 36 tháng có thời hạn được ghi, nhưng không đạt ngưỡng 60 tháng khi phạm vi đã xác định.
- 097–100: giữ xung đột NOXH/thương mại, dự án/địa chỉ/tài khoản và ngày giao cũ/mới.
  Có bảng vật liệu và nội quy thật trong PDF; không áp kết luận thiếu bảng của nhóm khác.
  Bảo trì phải tính đúng giá trước VAT; phép nhân 2% giá gồm VAT không tự thành đúng luật.
- 237–240: trụ sở và địa chỉ liên hệ có nhãn khác nhau nên không tự là mâu thuẫn;
  tên pháp nhân bên bán khác nhau vẫn là xung đột. Giá căn hộ và tổng hợp đồng là
  hai vai trò. Lịch chuẩn không xóa nhánh riêng đòi 5% cuối trước được cấp GCN.

Bốn family NOXH cũ **đã có criterion riêng** trong snapshot. Chúng được policy
`DRAFT_REVIEW` chiếu thành `UNKNOWN / OUTSIDE_REVIEW_SCOPE` vì cần hồ sơ chứng minh
đối tượng, điều kiện nhà ở/thu nhập hoặc cơ sở giá thực tế. C08 vẫn giữ disposition
ngoài phạm vi; không phải thiếu criterion, cũng không phải đã xác nhận đủ điều kiện.
Đây là đính chính cho phần giải thích sai trong bản xuất R6 ban đầu. Đáp án C07/C08
đã có đúng các criterion và disposition đó; không thay finding để sửa lời giải thích.

Bản xuất tại thời điểm R6: `/home/chienqt/Downloads/legal_compliance_GOLD_MASTER_20261115_R6/`.
Master có 60/360 ca đã biên soạn; TEAM có 48/300; TEST INPUTS có 60 PDF/C01,
không chứa đáp án. 48 ca đã phát hành ở R4 giữ nguyên byte. R5 là candidate nội bộ,
được thay bằng R6 trước phát hành để sửa diễn giải riêng của biến thể 36 tháng.
`full_e2e_gold_ready=false`: 300 ca còn chờ chấm, không phải 300 ca UNKNOWN pháp lý.

Các nguồn pháp lý bổ sung được tra từ [CSDL quốc gia về Thông tư 20/2016](https://vbpl.moj.gov.vn/boxaydung/Pages/vbpq-toanvan.aspx?ItemID=112528),
[BLDS 2015, Điều 688–689](https://vbpl.moj.gov.vn/toaannhandantoicao/Pages/vbpq-toanvan.aspx?ItemID=95942),
[Luật Xây dựng 2014](https://vanban.chinhphu.vn/?classid=1&docid=175348&pageid=27160)
và [Luật PCCC 2001](https://vanban.chinhphu.vn/?docid=80179&pageid=27160).
Tra cứu nguồn không phải gọi model gán nhãn bên ngoài.

## Đính chính phạm vi NOXH của bản R6

Rà trực tiếp toàn snapshot xác nhận **357/357 requirement versions đều có criterion**,
tổng cộng 479 criterion. Các mục `TC_NOXH_ELIGIBLE_PERSON_2015`,
`TC_NOXH_HOUSING_CONDITION_2015`, `TC_NOXH_INCOME_CONDITION_2015` và
`TC_NOXH_PRICE_BASIS_2015` đã có trong C07 của CA360_237–240, với disposition
`OUTSIDE_REVIEW_SCOPE`. C08 có liên kết tới đúng các criterion đó. Lời giải thích
trước đây nói chúng chưa có criterion là sai và đã được đính chính.

Bản xuất R6 gốc được giữ nguyên byte/checksum. Khi đọc README hoặc
`source_review.catalog_issues` của nhóm 237–240 trong gói R6, áp dụng đính chính tại:

```text
/home/chienqt/Downloads/legal_compliance_GOLD_MASTER_20261115_R6/ERRATA.md
/home/chienqt/Downloads/legal_compliance_GOLD_MASTER_20261115_R6/ERRATA_NOXH_SCOPE.json
/home/chienqt/Downloads/legal_compliance_GOLD_MASTER_20261115_R6/CATALOG_AND_COMPLETION_AUDIT.json
```

Không thay findings, evidence, PDF hoặc knowledge. Lượt rà soát này không chấm
thêm ca mới: vẫn 60 ca đã biên soạn theo phạm vi công bố, **300 ca thuộc 75 nhóm
nguồn còn chờ**. Không dùng việc lập mục lục/kiểm schema làm bằng chứng đã chấm
300 ca đó; `full_e2e_gold_ready=false`.


## Revision 15/11 R7 — nhóm 017–020 và 353–356

Bản xuất mới: `/home/chienqt/Downloads/legal_compliance_GOLD_MASTER_20261115_R7/`.
Đã biên soạn 68 ca; 292 ca thuộc 73 nhóm nguồn chưa chấm đủ. TEAM có 56/300 ca đã
biên soạn, 244 ca còn chờ; TEST vẫn 12/60 ca đã chấm, đáp án giữ riêng ở evaluator.
Không coi 292 ca chưa chấm là những hợp đồng thiếu căn cứ pháp lý.

### Nhóm 017–020: thương mại, mốc 20/10/2023

- Đọc đủ 37 trang, mọi thay đổi ba biến thể; xem ảnh trang 2, 18, 20, 24.
  Đối chiếu riêng 19 Điều của Mẫu 01/NĐ02/2022, gồm từng khoản và lựa chọn được
  thỏa thuận; không so mỗi tiêu đề hoặc ép số Điều của PDF giống mẫu.
- Giữ mâu thuẫn Thảo Điền/TP.HCM với dự án/đất giả lập Hà Nội. Địa chỉ trụ sở
  người bán thực sự trùng giữa thân và phụ lục, nên không bị gán mâu thuẫn theo
  địa chỉ dự án.
- Số tài khoản mua còn nằm trong ô bảo trì ở trang 2; phụ lục ghi một tài khoản
  bảo trì khác. Đáp án giữ CONFLICT và thiếu kỳ hạn gửi, không tự chọn tài khoản
  giúp đạt kiểm tra. Bảng vật liệu/bản vẽ và danh mục sở hữu cụ thể vẫn trống.
- Bản 018 thiếu giá/số tiền bảo trì nhưng còn tỷ lệ 2% trong một nhãn khác.
  Việc xóa câu về phạm vi giá cũng xóa nguyên nhân mâu thuẫn tương ứng: không
  kế thừa câu giải thích của baseline sau khi câu nguồn đã bị xóa.
- Bản 019 có quyền tăng giá đơn phương; bản 020 có hai giá cùng vai trò. Hai
  thay đổi được chấm bằng vị trí riêng của từng PDF, không bằng tên nhóm.
- Lịch 20/15/15/45/5 mới không tự xóa ngoại lệ thu 5% cuối khi chỉ đưa hồ sơ
  tự xin GCN. Phân biệt phương thức bàn giao với thông báo/thanh toán; không
  kích hoạt Điều 453 chỉ vì lịch nhiều đợt hoặc có bảo lưu sở hữu.

### Nhóm 353–356: NOXH, mốc 30/8/2025

- Đọc đủ 38 trang, mọi delta; xem ảnh trang 5, 9, 11, 12, 35.
- Giữ mâu thuẫn dự án/đất/trụ sở Khánh Hòa với phụ lục Hà Nội, năm hoàn thành
  2027 với ngày bàn giao 2025 và chỉ dẫn nộp bảo trì vào tài khoản/nộp cho bên bán.
- Xác định 7 occurrence viện dẫn văn bản chưa hiệu lực tại mốc kịch bản.
  Định danh đúng nhưng áp dụng quá sớm được ghi `INVALID / NOT_YET_IN_FORCE`;
  không gọi là STALE của văn bản đã hết hiệu lực. Không đổi ngày kịch bản để làm
  viện dẫn hợp lệ. Quyết định/GCN cá biệt chưa có bản nguồn vẫn giữ UNKNOWN.
- Bản 354 bỏ mã/tầng/diện tích ở cả thân và phụ lục; không suy diện tích từ phép
  chia giá/đơn giá hoặc lấy diện tích đất. Bản 355 ghi 36 tháng được giữ đúng ở
  facts, nhưng không tự ép finding khi C05 còn thiếu dữ kiện chuyển tiếp NOXH.
- Viện dẫn tên luật bị xuống block giữ hai đoạn nguồn chính xác, cùng checksum,
  theo thứ tự; không rút một tên chưa đủ thành tên luật hoàn chỉnh không có nguồn.
- Không áp Mẫu Ia thương mại máy móc cho NOXH. Các phiên bản cần xác định thủ tục
  chuyển tiếp trước 1/8/2024 vẫn giữ chưa phân giải khi nguồn chưa chứng minh.

### Đính chính ghi chú cũ và kiểm tra phát hành

Ghi chú sai về thiếu criterion NOXH của 237–240 đã được sửa ngay trong hồ sơ
biên soạn R7, thay vì chỉ có tờ đính chính bên ngoài. Đáp án/finding/evidence của
60 ca trước không đổi; 56 file case nguyên byte, 4 file chỉ thay hash receipt của
hai artifact có ghi chú được sửa. Giữ R6 và checksum gốc.

Có 44 kiểm tra ràng buộc nguồn và 47 test công cụ qua. Kiểm tra kỹ thuật không
phải một lượt thẩm định pháp lý độc lập thứ hai. Mọi ca ghi
`AI_SOURCE_ADJUDICATED`, `human_legal_signoff=false`, không gọi API/model khác.
Cam kết lưu/cấp bản sao trong7ngày được giữ thành fact riêng; GYC033 kiểm chứng việc thực hiện được để ngoài phạm vi dự thảo.
C07 thực sự được chấm có 5.246 mục: 3.767 SATISFIED, 171 VIOLATED, 153 MISSING,
1.155 UNKNOWN có lý do nguồn. 2.901 ngoài phạm vi, 331 không phát sinh điều kiện và
1.298 chưa phân giải scope được giữ riêng; không trộn 9.776 dòng thành accuracy.

Nguồn thời điểm đối chiếu từ [NĐ100/2024](https://vanban.chinhphu.vn/?docid=210760&pageid=27160),
[NĐ261/2025](https://vanban.chinhphu.vn/?docid=215594&pageid=27160),
[TT32/2025](https://chinhphu.vn/?classid=1&docid=215947&orggroupid=4&pageid=27160)
và hồ sơ văn bản chính thức được lưu cùng Master. Không thay workbook runtime,
PDF hoặc DB ứng dụng trong đợt chấm này.


## Revision 15/11 R8 — bốn nhóm nguồn được chấm trực tiếp

Bản xuất: `/home/chienqt/Downloads/legal_compliance_GOLD_MASTER_20261115_R8/`.
Thêm CA360_113–116, 229–232, 273–276 và 309–312, nâng lên **84 ca đã biên soạn,
276 ca chưa chấm đủ**. Có 44 DEV, 20 VALIDATION, 20 TEST đã chấm. TEAM có
64/300 ca đã chấm và 236 ca chờ; đáp án 20 ca TEST giữ riêng ở Master.
Không đổi PDF, knowledge, workbook seed, PostgreSQL runtime hoặc kết quả inference.

| Nhóm | Toàn văn baseline đã đọc | Nội dung phân biệt trong đáp án |
| --- | ---: | --- |
| 113–116, Xuân Thủy | 41 trang và toàn bộ delta | Ô kỳ hạn tiền gửi thiếu; ngưỡng diện tích/chậm còn trống; nhánh tự xin GCN đòi đợt cuối khác lịch mới; vật liệu chỉ có tiêu đề; 36 tháng bị chấm riêng |
| 229–232, Saigontel | 48 trang và toàn bộ delta | Dự án/địa chỉ khác tỉnh, hai chỉ dẫn tài khoản tiền mua, quyền đổi kênh thông báo riêng của bên bán; bản230 bỏ cả ngày giao kết và ngày GTC |
| 273–276, Linh Đàm | 38 trang và toàn bộ delta | Số hợp đồng điền nhầm nhánh mã doanh nghiệp; kỳ hạn còn trống; bảng vật liệu rỗng; NĐ23/2018 đã hết hiệu lực tại ngày kịch bản |
| 309–312, K-Homes | 42 trang và toàn bộ delta | Thân cho phép tài khoản khác được thông báo nên giữ tập tài khoản, không gọi nhiều tài khoản tự là xung đột; giá căn hộ gồm VAT nhưng bảo trì là cấu phần riêng; vị trí dự án vẫn mâu thuẫn |

Cả hai nhóm năm 2023 được đối chiếu từng Điều, nhánh và chú thích của 19 Điều Mẫu 01
NĐ 02/2022. Không dùng mỗi tiêu đề để xác nhận phù hợp. Các ô chưa điền trong nhánh
được chọn được ghi rõ; nhánh tổ chức hoặc song ngữ chưa chọn không bị ép hoàn thiện.
Các câu cam kết giao hồ sơ, mẫu biên bản nhận nhà và mẫu đề nghị thanh toán không
được sử dụng làm bằng chứng sự kiện đã xảy ra.

Riêng CA360_230, toàn văn đã bỏ ngày giao kết và GTC, còn những ngày về hồ sơ đất,
đăng ký doanh nghiệp và bàn giao dự kiến. Chúng có ý nghĩa khác, không thay mốc ký.
C05 vì vậy có300 mục UNKNOWN và23 không áp dụng; không sinh checklist C07 theo một
ngày đoán. C09 không kế thừa ngày 2020 từ baseline, các occurrence GTC bị xóa không
được dựng lại. Đây là đáp án thiếu dữ kiện thực trong nguồn, khác ca chưa được chấm.

Bảo hành 36 tháng của 115, 275, 311 và 231được đối chiếu đúng tối thiểu 60 tháng nhà chung
cư xây mới. Tiêu chí hỏi “có ghi thời hạn không” khác tiêu chí “đạt tối thiểu không”.
DS436 lấy việc kiểm tra/đo/ký biên bản, giữ kênh thông báo/thanh toán làm control
không liên quan. DS453 không tự phát sinh chỉ vì có nhiều đợt ứng trước xây dựng.

R8 có **6.705 C07 ASSESSED**:4.848 SATISFIED, 180 VIOLATED, 173 MISSING và 1.504
UNKNOWN có lý do nguồn. 3.486 ngoài phạm vi,406 không phát sinh điều kiện và1.298
chưa phân giải scope giữ riêng. Không gộp toàn bộ 11.895 dòng thành accuracy.

Có 81 kiểm tra ràng buộc nguồn và47 test công cụ qua; cả 68 file case của R7 giữ nguyên byte.
Đây là kiểm chứng kỹ thuật/nhất quán nguồn, không là một lượt thẩm định pháp lý
độc lập của người thật. Mọi ca ghi `AI_SOURCE_ADJUDICATED`, `human_legal_signoff=false`.
`full_e2e_gold_ready=false` vì 276 ca còn PENDING_ADJUDICATION. Pool relevance chỉ
là tập witness/control đã công bố, ngoài pool UNJUDGED; không công bố Recall@K
toàn văn từ một witness duy nhất.

Nguồn mới đối chiếu gồm [NĐ23/2018](https://vanban.chinhphu.vn/default.aspx?docid=193020&pageid=27160),
[NĐ67/2023](https://chinhphu.vn/?classid=0&docid=208599&pageid=27160),
[danh mục hết hiệu lực, mục 396](https://vbpl.vn/TW/Lists/HHTDanhMuc/Attachments/722/Danh%20m%E1%BB%A5c%202.pdf)
và [Luật sửa PCCC 40/2013](https://vanban.chinhphu.vn/default.aspx?docid=171412&pageid=27160).
Bản PDF/metadata và register được giữ trong hồ sơ tác giả. Tra cứu văn bản chính
thức không phải gọi API model sinh đáp án.

Với fact `purchase_account` của nhóm 309, giá trị KNOWN dạng danh sách là tập tài khoản
được nêu như các lựa chọn trong dự thảo có cơ chế đổi sau thông báo. Nó không xác nhận
một tài khoản đang hoạt động hoặc việc thông báo ngoài đời đã xảy ra. Không tự rút
danh sách này còn một số trước khi chấm câu hỏi về đầy đủ dữ liệu nguồn. Nhóm 229
không có cơ chế thay tương ứng và chỉ dẫn tiền mua khác nhau, nên được giữ CONFLICT.


## Revision 15/11 R9 — thêm tám ca có hồ sơ biên soạn trực tiếp

Bản xuất: `/home/chienqt/Downloads/legal_compliance_GOLD_MASTER_20261115_R9/`.
Thêm CA360_209–212 và bốn ca TEST được giữ đáp án trong Master evaluator.
Tổng **92 ca đã chấm theo phạm vi công bố, 268 ca PENDING_ADJUDICATION**.
Phân chia: 48 DEV, 20 VALIDATION, 24 TEST đã chấm; gói TEAM có 68/300 ca đã chấm,
232 ca chờ. Gói TEST INPUTS vẫn chỉ có 60 PDF/C01, không có đáp án.

Đọc toàn bộ 42 trang nhóm 209 và 41 trang nhóm TEST, chín phần toàn văn của mỗi nhóm,
tất cả delta của ba biến thể và kiểm ảnh tại các trang bản vẽ/bảng vật liệu liên quan.
Không sửa PDF, knowledge, workbook seed, PostgreSQL, code inference hay deployment.
84 case R8 giữ nguyên byte.

Ở nhóm DEV 209–212:

- Tên công ty ở phụ lục bị rút gọn; tên đầy đủ có trong thân và nội quy. Không tự tạo
  một pháp nhân khác từ tên rút gọn. Địa danh trong tên công ty không tự là trụ sở.
- Hai chỉ dẫn số tài khoản nhận tiền cùng vai trò không có điều khoản thay thế được
  giữ CONFLICT. Khác với nguồn cho phép chọn/đổi tài khoản bằng văn bản.
- Giá bán và tổng nghĩa vụ được đối chiếu theo đúng vai trò. Số VAT/giá đất còn
  thiếu nên không chia tổng cho 1.1 hoặc lấy nhãn 2% làm chứng minh cơ sở bảo trì.
- Bản 210 bỏ giá/đơn giá/số tiền bảo trì, nhưng 2% vẫn có trong thân và câu mới;
  không gán mất tỷ lệ chỉ vì parser literal không nhận đúng nhãn.
- Thời hạn 36 tháng trong 211 thay thời hạn nhà 60 tháng cũ; chấm mức tối thiểu khác
  câu hỏi có ghi thời hạn. Bản 212 giữ hai giá cùng vai trò, không tự chọn số thuận tiện.
- DS436 dùng hành vi đến kiểm tra/ký biên bản giao căn hộ, giữ FAX/thư/chuyển khoản
  làm control không liên quan. DS453 không phát sinh chỉ do chia nhiều đợt tiến độ.
- Đọc cả nội quy quản lý và giới hạn trách nhiệm dịch vụ đi kèm; không chỉ kiểm
  Điều 9 bảo hành rồi kết luận toàn bộ hồ sơ không có điều khoản loại trừ trách nhiệm.
- C09 phân biệt văn bản hết hiệu lực, tên văn bản đã định danh được trong cùng
  hồ sơ và giấy phép/biên bản cá biệt chưa cung cấp. Số hiệu trùng nhau của một
  Nghị quyết và một Luật không được tự gộp thành cùng văn bản.

Hồ sơ riêng của bốn ca TEST, curator và các nhãn tương ứng chỉ nằm trong Master,
không đưa vào gói TEAM. Tài liệu dùng chung này không công bố đáp án chi tiết TEST.

R9 có **7.393 C07 ASSESSED**: 5.370 SATISFIED, 218 VIOLATED, 177 MISSING,
1.628 UNKNOWN có lý do nguồn. 3.798 ngoài phạm vi, 438 không phát sinh điều kiện,
1.298 chưa phân giải phạm vi được giữ riêng. Không trộn chúng vào finding accuracy.
Pool retrieval là 30.139 witness/control đã chấm, ngoài pool vẫn UNJUDGED.

Có 98 kiểm tra nguồn/nhất quán biên soạn và 47 test công cụ qua. Chúng kiểm checksum,
quote/offset, riêng biệt case/split/policy và các phân biệt ý nghĩa đã chốt; không tự chứng minh
mọi nhận định pháp lý đúng. Nhãn biên soạn vẫn `AI_SOURCE_ADJUDICATED`,
`human_legal_signoff=false`, `production_outputs_used=false`,
`full_e2e_gold_ready=false`. Không gọi API hoặc model AI khác.

Nguồn đối chiếu mới:
[Luật Thương mại 2005, Điều 1(3)](https://www.vietnamtradeportal.gov.vn/kcfinder/upload/files/36.2005.QH11.pdf),
[lịch sử NĐ 51/2009](https://vbpl.moj.gov.vn/longan/Pages/vbpq-lichsu.aspx?ItemID=12001&Keyword=&dvid=259),
[lịch sử TT 06/2019](https://vbpl.moj.gov.vn/thuathienhue/Pages/vbpq-lichsu.aspx?ItemID=138879&Keyword=&dvid=301)
và [Luật Nhà ở 2014, Điều 183](https://vbpl.vn/FileData/TW/Lists/vbpq/Attachments/46742/VanBanGoc_65_2014_QH13.pdf).
Register ghi rõ tài liệu đọc qua kết quả tìm kiếm chính thức hay mở PDF thành công;
không tự ghi đã tải bản gốc khi đường tải không hoạt động.


## Revision 15/11 R10 — tám ca TEST được chấm trực tiếp

Tổng **100/360 ca** đã biên soạn theo phạm vi catalog, DRAFT_REVIEW và pool đã
công bố; **260 ca còn chờ**. Đọc toàn văn hai nhóm 46 và 42 trang, 23 phần text,
mọi delta của các biến thể và ảnh bảng/chỉ dẫn/thông báo liên quan.

Phân chia hiện tại: 48 DEV, 20 VALIDATION và 32 TEST đã chấm. Gói TEAM giữ nguyên
68/300 ca đã chấm, 232 ca chờ vì toàn bộ ca mới thuộc TEST. Không đưa curator,
source-review hoặc đáp án TEST vào TEAM. Nhãn chi tiết và hồ sơ đối chiếu chỉ
nằm trong Master evaluator.

R10 có **7.963 C07 ASSESSED**: 5.754 SATISFIED, 233 VIOLATED, 180 MISSING,
1.796 UNKNOWN do nguồn. 4.319 ngoài phạm vi, 474 không phát sinh điều kiện và
1.830 chưa phân giải scope được giữ riêng. Có 32.917 witness/control Retrieval
đã chấm; ngoài pool UNJUDGED. Không biến target chưa chấm thành UNKNOWN hoặc
coi thiếu hồ sơ chuyển tiếp là đã xác nhận không có chuyển tiếp.

Đối chiếu bổ sung ảnh trang 48–49 của Nghị định 96: Mẫu Ia có cơ chế điều chỉnh
phí vận hành hợp lý. Không được dùng riêng câu đó để tự kết luận một hợp đồng
vi phạm; phải đọc điều kiện, quyền lựa chọn và toàn bộ chỉ dẫn đi kèm. Hồ sơ chấm
lưu cả lần sửa nhận định này, trước khi phát hành checkpoint.

120 kiểm tra nguồn/nhất quán và 47 test công cụ đã qua. Không sửa PDF, knowledge,
workbook seed, DB ứng dụng hoặc code inference; 92 case R9 giữ nguyên byte.
Artifact, receipts, hashes và split được kiểm trước khi chọn mặc định
`data/private/gold -> gold_master_20261115_r10/`. Bản xuất nằm tại
`/home/chienqt/Downloads/legal_compliance_GOLD_MASTER_20261115_R10/`.
`full_e2e_gold_ready=false`; biên soạn `AI_SOURCE_ADJUDICATED`,
`human_legal_signoff=false`, không gọi model/API AI khác.

Metadata được đối chiếu từ [TT 06/2019](https://congbao.chinhphu.vn/van-ban/thong-tu-so-06-2019-tt-bxd-29957.htm)
và [NĐ 55/2024](https://chinhphu.vn/?classid=1&docid=210254&pageid=27160&typegroupid=4),
cùng nội dung luật trong snapshot đã khóa. Register phân biệt nguồn đã đọc nội
dung, metadata đã kiểm và phạm vi trang PDF thực sự đã đọc; không ghi đã đọc
trọn văn bản pháp luật khi chỉ mới tải được file.
