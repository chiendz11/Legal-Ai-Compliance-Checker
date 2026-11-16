# Đáp án Gold: phạm vi đã đối chiếu và phần còn thiếu — 10/11/2026

Tài liệu này mô tả gói **v1**. Xem [đợt biên soạn trực tiếp v3](gold_direct_curation_20261110.md)
cho coverage mới; cả hai gói vẫn chưa hoàn tất Gold toàn pipeline.

Trạng thái hiện tại là **PARTIAL_GOLD**, chưa phải bộ Gold đầy đủ để chấm
end-to-end toàn hệ thống. Các file được tạo riêng trong:

```text
/home/chienqt/Downloads/legal_compliance_gold_v1_20261110/
```

## 1. Gold trong dự án này có nghĩa gì?

Gold là đáp án đã được lập và đối chiếu cho **một câu hỏi cụ thể**, từ PDF nguồn,
tri thức đã khóa và căn cứ được ghi lại. Việc engine chạy thành công, workbook
đúng schema hoặc một cột có `human_verified=true` chưa tự chứng minh đáp án đúng.

Chủ dự án đã chấp nhận dùng AI để biên soạn và đối chiếu pháp lý. Bản phát hành
ghi nhận sự chấp nhận đó bằng `owner_accepted_ai_curation=true`; người biên soạn
được ghi là AI. `human_legal_signoff=false` thể hiện chưa có hồ sơ một luật sư
độc lập đọc và ký xác nhận từng đáp án. Không cần xin lại phê duyệt cho cùng
phạm vi đã được chủ dự án giao.

Ví dụ hai câu hỏi khác nhau:

- “Phụ lục giao dịch ghi thời hạn bảo hành bao nhiêu tháng?” là câu hỏi trích xuất.
- “Điều khoản bảo hành của hợp đồng này đáp ứng luật áp dụng chưa?” còn cần
  xác định phạm vi, thời gian, phiên bản luật và hiệu lực của các điều khoản.

Gold cho câu hỏi thứ nhất không tự trở thành Gold cho câu hỏi thứ hai.

## 2. Khóa nguồn và phiên bản

| Thành phần | Phiên bản/phạm vi |
| --- | --- |
| PDF nguồn | `PDF360_DRAFT_GTC_V4_R2_20261110` |
| Số tài liệu | 360 PDF, 90 nhóm nguồn, 18.660 trang |
| Knowledge | `V750_KNOWLEDGE_OWNER_APPROVED_20261110` |
| Knowledge SHA-256 | `4ab2d7ea296ea908e25c09fcb6d5f073f1ebe1917678b36390f803b1c725804a` |
| Chế độ đánh giá | `DRAFT_REVIEW`; các dữ kiện synthetic không chứng minh giao dịch đã thực hiện |
| Bộ đáp án mới | `PROJECT_GOLD_SCOPED_V1_20261110` |

PDF được đọc lại bằng PyMuPDF, tách khỏi parser của ứng dụng. Đã đối chiếu lại
checksum PDF; 360 tài liệu không có trang thiếu lớp văn bản trong lần kiểm tra
này. Điều đó xác nhận khả năng đọc text, chưa tự xác nhận thứ tự đọc/bố cục và
mọi nội dung pháp lý đều đã được hiểu đúng.

Mỗi đoạn chứng minh có `source_sha256`, `page`, `ref`, `start`, `end`, `quote`.
Các vị trí thuộc bộ nguồn độc lập, không phụ thuộc `chunk_id` của Retrieval.
Khi đổi chunker, evaluator vẫn có thể đối chiếu về cùng PDF và đoạn nguồn.

## 3. Những phần đã có Gold

### 3.1. Giá trị ghi trong phụ lục giao dịch: 360 tài liệu

Có 36 trường mỗi tài liệu, tổng cộng **12.960 đáp án**:

| Trạng thái | Số lượng | Ý nghĩa |
| --- | ---: | --- |
| `KNOWN` | 12.625 | Có giá trị đọc được tại nhãn của phụ lục |
| `NOT_PROVIDED_IN_AUTHORED_APPENDIX` | 245 | Phụ lục không cung cấp giá trị này |
| `CONFLICT` | 90 | Phụ lục chứa hai giá bán khác nhau cho cùng vai trò |

Các trường gồm thông tin các bên, mã hợp đồng, ngày giả định, căn hộ, diện tích,
thửa đất, giá, tài khoản, bảo hành và bảo trì. Giá trị được lập lại từ văn bản
PDF; không lấy từ C02/C07 đã chạy hoặc từ tên nhóm biến thể.

**245 trường không được cung cấp trong phụ lục không phải 245 dữ kiện thiếu
trong toàn hợp đồng.** Thân mẫu có thể vẫn ghi thông tin đó. Không dùng trạng
thái này để chấm C02 toàn văn là sai hoặc để sinh `MISSING` tại C07.

Giá tiền giữ số thập phân và đơn vị; số định danh, điện thoại, tài khoản giữ
kiểu chuỗi và số 0 đầu. Hai giá xung đột được giữ cùng nhau.

### 3.2. Lượt xuất hiện số hiệu văn bản: 360 tài liệu

Đã lập **4.569 lượt xuất hiện** cùng vị trí nguồn. Phạm vi này chỉ bao gồm dạng
số hiệu được khai báo: luật QH, nghị định NĐ-CP, thông tư TT-BXD/TT-NHNN.

Đây là Gold cho việc tìm **số hiệu xuất hiện ở đâu**. Nó chưa chấm được:

- Viện dẫn chỉ ghi tên luật, tên rút gọn hoặc viết sai số hiệu.
- Văn bản đó có tồn tại, còn hiệu lực hay phù hợp giao dịch không.
- Toàn bộ nội dung Điều/Khoản/Điểm được dẫn có được hiểu đúng không.

Không gán `VALID` chỉ vì tìm được một số hiệu. Khi đo extraction, các viện dẫn
ngoài phạm vi đã gán nhãn phải được giữ `UNJUDGED`, không tự tính thành false positive.

### 3.3. Hai tiêu chí bảo hành: ba ca đã đối chiếu riêng

Đã lập đáp án cho `CA360_001`, `CA360_003`, `CA360_004`:

| Ca | Thời hạn ghi trong phụ lục | `TC_PV_HYC053_01` | `TC_PV_HYC053_02` | `FAM_WARRANTY_MIN_60` |
| --- | ---: | --- | --- | --- |
| CA360_001 | 60 tháng | SATISFIED | SATISFIED | COMPLIANT |
| CA360_003 | 36 tháng | VIOLATED | SATISFIED | NON_COMPLIANT |
| CA360_004 | 60 tháng | SATISFIED | SATISFIED | COMPLIANT |

Phạm vi: nội dung cam kết bảo hành tại mốc giao kết **giả định 16/02/2017**;
phiên bản `PV_HYC053`. Bản luật chính thức được tải và đối chiếu bằng hình ảnh
tại trang 42, Điều 85 khoản 2 của
[Luật Nhà ở 65/2014/QH13](https://datafiles.chinhphu.vn/cpp/files/vbpq/2014/12/65.signed.pdf).

Đã kiểm tra điều khoản phụ lục nói rõ việc thay thế thời hạn bảo hành trong
thân mẫu. Mốc bắt đầu được ghi là nghiệm thu hoàn thành đưa nhà ở vào sử dụng.
Không có kết luận rằng căn hộ thực tế đã nghiệm thu hoặc người bán đã thực hiện
bảo hành. Xung đột về giá tại CA360_004 không làm mất căn cứ của tiêu chí bảo
hành không phụ thuộc giá.

Đây là **6 quyết định criterion và 3 kết quả requirement cho một nhóm nghiệp vụ**,
không phải xác nhận toàn bộ ba hợp đồng tuân thủ. Không đưa CA360_002 vào phần
Gold pháp lý này khi việc phân giải mốc của ca đó chưa được thẩm định riêng.

## 4. Những phần chưa được nâng Gold

Các phần sau còn `PENDING_ADJUDICATION`; đáp án engine trong MASTER cũ vẫn là
SILVER reference:

| Phần | Việc còn phải đối chiếu độc lập |
| --- | --- |
| C02 toàn văn | Facts từ cả thân và phụ lục; tư cách, phạm vi, giá trị và xung đột thực sự |
| C04–C05 | Scope, mốc chọn luật, phiên bản và chuyển tiếp của từng requirement |
| C06 | Các đoạn liên quan và các cách chứng minh thay thế; nhóm evidence chống lại kết luận |
| C07–C08 toàn bộ | Điều kiện, ngoại lệ, nội dung bị cấm, thiếu nội dung, numeric và tổng hợp |
| C09 xác thực | Định danh, ngày hiệu lực, domain và cách hiểu từng viện dẫn |
| C10–C11 | Loại rủi ro, mức độ, provenance và hành động khắc phục phù hợp |
| C12 | Hành vi reviewer, trạng thái chờ duyệt và thay đổi quyết định; không tự tạo hành vi của người thật |
| C13 | Tính đầy đủ, nhất quán và căn cứ của báo cáo; không chấm bằng cách khớp nguyên văn câu của LLM |

Chưa có mẫu số chính xác cho toàn bộ C07 trước khi chốt C05. Không lấy
`479 × 360` làm số criterion bắt buộc phải đánh giá, vì các phiên bản và điều
kiện áp dụng khác nhau.

## 5. Vì sao chưa gắn Gold cho toàn bộ?

Trong lần gán nhãn thử độc lập, model đã đề xuất sai rằng CA360_003 chứa đồng
thời thời hạn 60 và 36 tháng trong phụ lục. Đối chiếu PDF xác nhận tại nhãn
đang xét chỉ có 36 tháng. Trích dẫn sai bị chặn; đề xuất đó không được đưa vào
gói Gold. Bộ gán nhãn riêng cũng gặp HTTP 429/503; các lượt không hoàn tất
được giữ là lỗi annotation, không biến thành đáp án pháp lý `UNKNOWN`.

Model dự phòng trả lời được một yêu cầu nhỏ chưa chứng minh đã có đủ tài nguyên
và chất lượng để thẩm định toàn bộ các mục còn lại. Không có tuyên bố đã hoàn
thành đối chiếu hai model trên toàn bộ 360 ca.

Vì vậy, `GOLD_COVERAGE.json` ghi:

```json
{
  "release_status": "PARTIAL_GOLD",
  "full_e2e_gold_ready": false,
  "old_silver_outputs_promoted": 0,
  "db_seed_performed": false,
  "benchmark_executed": false
}
```

## 6. File nào dùng vào việc gì?

| File/thư mục | Công dụng |
| --- | --- |
| `GOLD_SCOPED_MASTER.xlsx` | Xem phạm vi Gold của 360 ca; chỉ evaluator giữ đầy đủ |
| `GOLD_SCOPED_DEV_VALIDATION.xlsx` | 300 ca DEV/VALIDATION; đáp án của các tác vụ được nêu rõ |
| `GOLD_SCOPED_TEST_EVALUATOR_ONLY.xlsx` | 60 ca TEST; giữ riêng với evaluator |
| `literal_gold/` | JSON đáp án giá trị phụ lục và lượt số hiệu |
| `legal_gold/` | Sáu quyết định criterion đã đối chiếu cho ba ca bảo hành |
| `adjudications/` | Người biên soạn AI, nguồn, phiên bản và cách ra quyết định |
| `GOLD_COVERAGE.json` | Phần nào Gold, phần nào chưa; giới hạn sử dụng benchmark |
| `GOLD_VALIDATION.json` | Kết quả kiểm hash, quote, ownership và split |
| `PENDING_LAYERS.jsonl` | Các lớp chưa hoàn tất theo từng ca; không phải danh sách vi phạm |

Workbook này là **đáp án evaluator**, không thay workbook runtime để seed.
Ứng dụng tiếp tục dùng dataset v4 r2 đã chốt. Việc đổi đáp án không tự đổi PDF,
DB, báo cáo lịch sử hoặc manifest tải dataset của cả nhóm.

## 7. Cách hoàn tất Gold cho toàn bộ pipeline

1. Lập facts và scope/time từ toàn văn cho từng ca; khóa kết quả C05 trước khi
   xác định checklist criterion cần chấm.
2. Biên soạn câu trả lời từng criterion từ đúng điều luật và PDF. Người/model
   gán nhãn không được nhìn output của pipeline đang được đánh giá.
3. Đối chiếu lại đáp án với nguồn. Khi hai lượt annotation bất đồng, xử lý
   riêng từng bất đồng; trạng thái pháp lý `UNKNOWN` cần lý do thiếu dữ kiện
   thật, không dùng thay cho một annotation chưa hoàn tất.
4. Với `MISSING` hoặc “không có điều khoản bị cấm”, phải xác nhận phạm vi đọc
   toàn tài liệu và phụ lục. Không dùng Retrieval top-K rỗng làm bằng chứng vắng.
5. Khóa các evidence chấp nhận được theo vị trí PDF; ghi rõ pool đã chấm và
   phạm vi chưa chấm. Một witness không tự là toàn bộ đáp án relevance.
6. Từ C07/C09 đã đối chiếu, lập C08/C10/C11 và các assertion của C13 theo chính
   sách đã công bố; không sao chép output engine thành đáp án.
7. Chỉ phát hành `full_e2e_gold_ready=true` khi bảng coverage của tất cả các lớp
   đã đủ, kiểm tra riêng DS436_01, DS453_02 và các viện dẫn còn mơ hồ.

Tập TEST giữ tách theo nhóm PDF nguồn, cùng các biến thể của một nguồn nằm trong
cùng split. Nếu thành viên đã xem MASTER hoặc đáp án của TEST trước đây, phải
ghi nhận việc đó; không gọi lần đánh giá sau là kiểm thử mù hoàn toàn.

## 8. Code hỗ trợ kiểm tra

[`devtools/gold_answers.py`](../../backend/src/devtools/gold_answers.py) kiểm tra
provenance và cấu trúc cho các target được khai báo. Nó không tạo kết luận tuân
thủ và không chứng minh ngữ nghĩa pháp lý chỉ bằng việc validate JSON thành công.

Chạy kiểm tra các trường hợp sai thường gặp:

```bash
source .venv/bin/activate
python -m pytest backend/tests/unit/test_gold_answers.py -q
```

Bộ kiểm tra chặn quote sai, lẫn PDF/hash, đổi requirement của criterion, bỏ qua
phạm vi đọc khi khẳng định vắng nội dung, chọn một giá thuận lợi từ xung đột và
gán nhầm annotation lỗi thành Gold UNKNOWN.
