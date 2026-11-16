# Baseline v4 r2: dữ liệu đã sửa và kết quả demo ngày 10/11/2026

> Bản ghi lịch sử: trạng thái dataset/approval trong đợt này đã được cập nhật bởi
> [release PDF360 v4 r2 và knowledge được chủ dự án duyệt](dataset_pdf360_v4r2_runtime_20261110.md).


Tài liệu này tiếp nối [thay đổi mặc định dân sự và PDF v4](baseline_v4_civil_defaults_20261109.md).
Phạm vi là rà soát **dự thảo trước khi ký** (`DRAFT_REVIEW`). Kết quả inference
vẫn là bản máy đề xuất, chưa phải quyết định human review hoặc báo cáo đã phát hành.

## 1. Kết quả demo HD360_001

Đã upload PDF thật qua UI, chạy queue, Documents → Scope/Temporal → Citation →
Retrieval → Compliance → Risk → Recommendation → Report. Không lấy đáp án QA làm
output của module. Nguồn là `NEW_001BF40B2491_S01.pdf`, 79 trang.

- Ca: `CA_UP_B5BE778D0384`.
- Run: `RUN_dfd704ad7c3c455ab067d07534bb76dc`.
- Báo cáo: `REPORT_48da32fb-461e-579f-9fe8-c811f1f08b42`.
- [Mở báo cáo local](http://app.legal-checker.localhost:18880/reports/REPORT_48da32fb-461e-579f-9fe8-c811f1f08b42).
- PDF SHA-256: `34ac97fbcb32dfd2477d09de9154ce0d13b0d681ef9bbdbd69a04a391fb240cb`.
- Knowledge: `V750_CIVIL_DEFAULTS_20261109`, hash
  `3b8f12a619f8ab017d7d71957d5e07ded651d75f8205a8dbe338abe402ed7042`.

| Kết quả hiển thị | Số lượng |
| --- | ---: |
| Yêu cầu tuân thủ | 59 |
| Yêu cầu ngoài phạm vi rà soát dự thảo | 14 |
| Yêu cầu không phát sinh điều kiện | 2 |
| Yêu cầu chưa đủ căn cứ / không tuân thủ | 0 / 0 |
| Criterion đáp ứng | 84 |
| Criterion ngoài phạm vi | 39 |
| Criterion được loại trừ theo điều kiện | 6 |
| Viện dẫn VALID / UNKNOWN | 12 / 0 |
| Rủi ro / khuyến nghị phát sinh | 0 / 0 |

Hai mục từng gây hiểu nhầm được kiểm riêng:

1. **Phương thức bàn giao — DS436_01:** SATISFIED, evidence có quy trình kiểm tra/
   ký biên bản/nhận bàn giao. Không dùng Fax/thư, hoặc chỉ ngày và địa điểm để chứng minh.
2. **Bảo lưu sở hữu — DS453_02:** không phát sinh điều kiện trong ca này. Phần giữ
   lại tiền trước cấp giấy chứng nhận không tự chứng minh giao dịch mua chịu;
   câu cho phép bảo lưu sở hữu cũng không tự chứng minh vi phạm.

Mốc điều kiện giao dịch chung HYC015_02 và ba thông tin tài khoản bảo trì
ACCOUNT_2015_03 đều có quote nguồn tương ứng. Run mất khoảng **6 phút 13 giây**;
227 quote được kiểm khớp chính xác offsets. Có hai lỗi HTTP tạm thời trong audit;
luồng retry đã phục hồi. Không giấu các báo cáo lỗi/UNKNOWN của lần chạy trước.

Đã mở tám tab, không có lỗi trang hoặc HTTP trong lượt kiểm UI. Xuất JSON/PDF/DOCX
đều HTTP 200. Cả 27 báo cáo có trước run này giữ nguyên checksum; tổng hiện có 28.
Báo cáo mới giữ `DRAFT/PENDING`, không tự CONFIRM, OVERRIDE hoặc publish.

## 2. Phần code bổ sung để xử lý những lỗi còn lại

| Phần | Sửa gì | Tại sao cần sửa |
| --- | --- | --- |
| Documents / `profile_extractor.py` | Ba nhãn riêng cho số, tên và ngân hàng tài khoản bảo trì; xử lý tên xuống dòng và khoảng trắng kép | Dữ liệu đã có trong PDF nhưng regex cũ bỏ sót hoặc chỉ đọc dòng đầu |
| Compliance / `content_verifier.py` | Kiểm nội dung hữu hạn cho `TC_ACCOUNT_2015_03`, đúng version 2015 | Có đủ nguồn để kiểm trường thông tin dự thảo; không cần LLM đoán thông tin ngân hàng |
| Retrieval | Anchor chạy trên nguyên văn, giữ parent context và giới hạn đoạn đại diện cho kiểm nội dung bắt buộc | Tránh chọn Điều Thông báo thay Điều Giao nhận hoặc đưa quá nhiều đoạn vào một lượt gọi |
| Knowledge / decision rules | Predicate DS436/DS453 đúng nội dung và target đánh giá | Tách điều khoản được luật cho phép khỏi vi phạm thực hiện cần chứng cứ thực tế |
| Reasoning | Kiểm riêng evidence của đề xuất VIOLATED do LLM | Quote có thật nhưng sai chủ thể/điều kiện chưa đủ làm căn cứ kết luận vi phạm |

Producer cuối là `documents.rules-v10`, verifier `C07_EXACT_CONTENT_V3`. Producer
chỉ ghép tối đa ba dòng tiếp theo trong cùng chunk khi có nhãn tài khoản kế tiếp
làm điểm dừng. Không nối qua chú thích/tiêu đề; không mở rộng vô hạn. Canonical
value gộp khoảng trắng, nhưng quote và offsets vẫn giữ nguyên văn bản gốc.

Ba thông tin bảo trì được tách khỏi tài khoản nhận tiền mua nhà. Nhãn không đúng
vai trò, placeholder, giá trị chưa rõ, nhiều giá trị mâu thuẫn hoặc fact sai quote
không được chấp nhận. Nhánh kiểm này xác nhận **thông tin ghi trong dự thảo**;
không xác nhận ngân hàng giả lập có giấy phép, tài khoản thật đã mở hay tiền đã thu.

Run E2E bên trên dùng producer `rules-v9` cho HD360_001. Bổ sung `rules-v10` xử lý
tên nhiều dòng/khoảng trắng trên corpus; HD360_001 không bị thay PDF/hash. Phải giữ
phiên bản extraction trong audit, không sửa run cũ thành run của producer mới.

## 3. PDF v4 r2 sửa thêm những gì?

Gói: `PDF360_DRAFT_GTC_V4_R2_20261110`, 360 PDF từ 90 nguồn, vẫn có bốn nhóm 90 file.
Thư mục local:

```text
/home/chienqt/Downloads/hop_dong_synthetic_4_bien_the_v4_source_checked/
```

V4 đã điền thêm 407 vùng có nhãn, trong đó 136 vùng mở rộng vào khoảng trắng an
toàn ở chữ 9,5 pt; 72 vùng không an toàn giữ fallback. V4 cũng có phụ lục riêng
xác định bộ điều kiện chung và ngày dự kiến áp dụng, tách khỏi nội quy chung cư.
Biến thể cố ý thiếu ngày không được bổ sung ngày qua phụ lục này.

R2 sửa thêm:

- **33 nguồn / 132 PDF:** sửa tên bên bán hoặc cách dựng chữ trong phụ lục do bộ
  sinh v3 lấy câu mô tả, tên bị cắt hoặc tên công ty trong phần căn cứ. Ưu tiên
  phần ghi rõ Bên bán; hai trường hợp bổ sung đối chiếu tên giữa các bên trên bìa.
- Có 31 sửa tên theo vai trò; hai trường hợp thêm xử lý Unicode: dựng NFC để chữ
  tiếng Việt không mất dấu. Một trong hai tên còn thiếu dòng tên riêng nên được
  bổ sung từ chính mẫu nguồn. Đây không phải tra cứu/xác nhận đăng ký doanh nghiệp.
- **8 ô tên tài khoản do bộ sinh cũ điền sai hoặc cắt tên:** gỡ giá trị synthetic
  cũ, ghi dẫn đến tên đúng trong Phụ lục 01. Không đè tên mới lên tên sai để tạo hai
  dữ kiện xung đột trong baseline.
- **4 ô của cùng một nguồn:** đổi số nhận tiền mua nhà đã điền nhầm vào đoạn bảo
  trì thành mã tài khoản bảo trì riêng. Không thay nội dung điều khoản nguồn.
- Tái dựng phần phụ lục synthetic bị ảnh hưởng, cập nhật SHA-256, số trang và log.
  Bản v2/v3 giữ nguyên; bản v4 trước sửa được lưu riêng để đối chiếu.

Không tạo chữ ký, con dấu, giấy phép, quyết định phê duyệt hoặc biên nhận mới.
Không biến hợp đồng nhà ở xã hội thành nhà ở thương mại. Các biến thể thiếu thông
tin, bất lợi và mâu thuẫn vẫn giữ thay đổi có chủ đích; không ép cả bốn nhóm tuân thủ.

## 4. Các workbook và file trong gói dùng để làm gì?

| File | Mục đích |
| --- | --- |
| `PDF360_SOURCE_INDEX_V4.xlsx` | Tra HD360 → PDF, hash mới/cũ, nhóm, vị trí phụ lục; xem log điền và sửa chủ thể |
| `BASELINE_90_SOURCE_REVIEW.xlsx` | Kiểm dữ kiện/nguồn trên 90 baseline và ghi những trường hợp cần rà thêm |
| `C02_BANK_EXTRACTION_90.xlsx` | Đối chiếu 270 trường số/tên/ngân hàng từ PDF thật bằng producer hiện tại |
| `KNOWLEDGE_CIVIL_DEFAULTS_20261109.xlsx` | Xem 18 bảng knowledge và thay đổi hai nhóm rule dân sự |
| `PARTY_ROLE_CORRECTIONS_20261110.json` | Giá trị trước/sau, quote/trang nguồn và hash theo từng file sửa |
| `VALIDATION.json`, `SHA256SUMS` | Kiểm giữ nguồn và tính toàn vẹn của 360 PDF |
| `DEMO_HD360_001_ACCEPTANCE.json` | Chỉ số nghiệm thu của run thật; không dùng làm gold toàn catalog |

Đây là các workbook **rà soát nguồn/knowledge**, không phải workbook runtime đầy
đủ để chạy `scripts.local_db seed`. Không đổi manifest TEAM sang một file index.

## 5. Mức kiểm chứng và giới hạn

- Kiểm 90 baseline độc lập với reasoner: 1.440 kiểm tra nguồn/dữ kiện đạt. Phạm vi
  gồm số học, thông tin dự thảo, diện tích tách biệt, warranty và mốc điều kiện chung.
- Kiểm C02 dùng implementation Documents thật trên cả 90 PDF, không đọc facts đã
  seed vào DB: **270/270 trường đạt**. Trạng thái fact vẫn là máy trích xuất, không
  human verified. Kiểm so sánh Unicode NFC giữ dấu, không bỏ dấu để làm metric đẹp.
- Đối chiếu 360 file về hash, hình ảnh, kích thước/trang và nguyên văn mẫu nguồn.
  Vùng sửa text synthetic có log riêng; kiểm pixel ngoài vùng được phép của những
  trang đó. Phụ lục do bộ sinh tạo được so với dữ liệu dựng mới, không giả vờ giữ
  nguyên phụ lục sai của v3.
- Kiểm nguồn không chứng minh toàn bộ 90 baseline tuân thủ toàn catalog. Có 88/90
  nguồn tìm được ứng viên quy trình bàn giao bằng bộ dò nguồn; hai trường hợp còn
  lại cần đọc ngữ nghĩa. Không gọi hai trường hợp này là vi phạm hoặc tự gán đáp án.
- Viện dẫn lịch sử/chuyển tiếp vẫn cần đối chiếu ngữ cảnh; các số dò interval trong
  workbook không phải số vi phạm pháp luật.

Backend được kiểm trên PostgreSQL test riêng; không truncate DB ứng dụng. Kết quả
cuối: **1.686 test pass, 7 skip**; Ruff lint/format của phần sửa đều pass. Chi tiết
được lưu trong private evidence, ngoài Git. Tests và demo một ca không thay thế
đánh giá độc lập từng criterion trên cả tập TEST.

## 6. Điều gì đã dùng trong ứng dụng, điều gì chưa phát hành?

Ứng dụng local đã dùng knowledge revision nêu trên và PDF v4 cho ca upload mới.
API/worker/scheduler dùng cùng backend image local. Báo cáo cũ giữ đúng source,
knowledge hash, extraction version và kết quả của lần chạy cũ.

Full dataset seed vẫn là **TEAM_BASELINE_20261107**, thêm knowledge revision qua
lệnh `align-content-defaults`; chưa có full runtime/QA của 360 PDF v4 r2. Link
Supabase cũ chưa chứa bytes v4 r2, và ZIP DEV/VALIDATION trên Drive chưa được thay
trong đợt này. Không đổi URL/hash rồi tái dùng chunks, offsets và đáp án cũ.

Khi phát hành seed kế tiếp, phải dùng PDF cuối làm nguồn để dựng lại C02/C03/C04,
scope/temporal, C06, C07–C13 và payload QA; giữ split theo nguồn gốc, tách TEST khỏi
đáp án. Sau khi kiểm FK/hash/schema/lineage và nội dung tham chiếu mới cập nhật
manifest tải, DB baseline và tài liệu onboarding.

Hiện thay đổi code nằm local trên `feat/integration-contract-alignment`, chưa
commit/push. Rollout image local không phải CI/GHCR đã publish hay GitOps đã sync
revision mới; Argo auto-sync được giữ theo trạng thái thử local hiện có.
