# Thay đổi tri thức từ workbook USER_REVIEWED — 06/11/2026

Bản tiếp theo đã chốt: [TEAM_BASELINE_20261107](dataset_team_baseline_20261107.md). Các khoảng trống và trạng thái chưa phát hành dưới đây mô tả revision 06/11, không phải danh sách đang mở của baseline 07/11.

## 1. Kết quả và phạm vi

Đã tạo revision `V750_LEGAL_KNOWLEDGE_ALIGNED_20261106` dựa trực tiếp trên ba
workbook trong ZIP `WORKBOOKS_USER_REVIEWED_20261105.zip` do chủ dự án cung cấp.
Đã đối chiếu nội dung knowledge từ workbook MASTER với snapshot reviewed cũ:
hai nguồn có cùng hash, không dùng một bản JSON khác phiên bản để sửa dữ liệu.

Revision giữ **306 requirement families, 343 versions và 441 criteria**. Không
sửa nguyên văn luật, ngưỡng numeric, ngày hiệu lực hoặc tự tạo đáp án tuân thủ.
Phần được sửa là cách mô tả mốc/chuyển tiếp, tên dữ kiện scope, liên kết nguồn và
trạng thái khoảng trống đã lỗi thời. Tài liệu quy ước chính:
[knowledge_applicability_policy.md](../contracts/knowledge_applicability_policy.md).

Các file nằm ngoài Git tại:

```text
/home/chienqt/Downloads/legal_compliance_v750_knowledge_aligned_20261106/
```

| File | Dùng để làm gì? |
|---|---|
| `01_KNOWLEDGE_ALIGNED_20261106.xlsx` | Đọc 22 bảng tri thức/quản trị tri thức, ma trận policy và giới hạn; file nhỏ, không phải workbook đầy đủ để seed runtime |
| `*MASTER_KNOWLEDGE_ALIGNED_20261106.xlsx` | Toàn bộ knowledge mới cùng dữ liệu runtime/QA lịch sử của 360 ca |
| `*DEV_VALIDATION_KNOWLEDGE_ALIGNED_20261106.xlsx` | Cùng revision tri thức và runtime/QA lịch sử của 300 ca DEV/VALIDATION |
| `*TEST_INPUTS_KNOWLEDGE_ALIGNED_20261106.xlsx` | Cập nhật knowledge dùng chung; giữ nguyên tập đầu vào TEST, không thêm đáp án |
| `REQUIREMENT_POLICY_MATRIX.csv` | 343 dòng: family/version/group, loại ngày, sự kiện thực hiện, chuyển tiếp, nguồn và khoảng hiệu lực |
| `CELL_CHANGES.csv` | Before/after và lý do từng thao tác chỉnh sửa; thao tác thêm dòng có `column=__row__` |
| `KNOWLEDGE_ALIGNMENT_MANIFEST.json` | Hash knowledge, checksum từng workbook và phạm vi revision |
| `KNOWN_LIMITS.json` | Những khoảng trống thật còn tồn tại, không bị đóng theo cờ đã duyệt |
| `VALIDATION.json` | Kết quả kiểm checksum, nguồn, khoảng hiệu lực, khóa ngoại và bảo toàn runtime/QA |

Knowledge hash mới:

```text
1852c4695aac37645a3660fcbac9575fc7d45dafc7eecb4a51f11e63b501ff18
```

Hash cũ vẫn nằm trên các case/run/QA lịch sử:

```text
df6ed7aa9f5100bfe68430b950d55542db752e7255c324e18be171ce0d0d3ade
```

## 2. Những thay đổi trong workbook

### 2.1. Phiên bản yêu cầu: không còn marker mơ hồ

`phien_ban_yeu_cau.loai_moc_ap_dung` được chuẩn hóa:

| Marker | Số versions | Ý nghĩa trong contract review |
|---|---:|---|
| SIGNING | 337 | Ngày xác lập hợp đồng/văn bản đang xét |
| TEMPLATE_USE | 5 | Ngày sử dụng/công khai mẫu; cần nguồn riêng |
| DEPOSIT_AGREEMENT | 1 | Ngày xác lập thỏa thuận đặt cọc |

Không gán một ngày giả lập mới cho bất cứ hợp đồng nào. `337 SIGNING` là cách
chọn chế độ pháp luật của **hợp đồng tại lúc xác lập**; không có nghĩa thời hạn
thực hiện, bảo hành, thu tiền hoặc bàn giao đều bắt đầu vào ngày ký.

`quy_tac_chuyen_tiep` được chuyển từ prose chung sang JSON có schema/policy ID.
Mỗi version ghi review scope, marker chọn chế độ, sự kiện thực hiện liên quan,
nguồn, nhánh chuyển tiếp và tình trạng đã có criteria. Vì cột vẫn là TEXT nên
không thay cấu trúc SQL, nhưng consumer phải dùng resolver mới để hiểu metadata.

Đã đối chiếu Điều 83 Luật KDBĐS, Điều 80 Luật BVQLNTD, Điều 198 Luật Nhà ở và
mốc hiệu lực được sửa bởi Luật 43/2024. Link nguồn và giới hạn diễn giải nằm
trong policy. Đặc biệt, chuyển tiếp thủ tục bán nhà đủ điều kiện từ trước không
tự biến mọi điều khoản của hợp đồng mới thành điều khoản theo luật cũ.

### 2.2. Scope: có cùng tên field giữa catalog và C02

- Giữ chín scope records dùng `la_giao_dich_dien_tu`; bổ sung thuộc tính nullable
  tương ứng vào C02.
- Đổi năm scope records từ `can_danh_gia_trong_tai` thành
  `co_thoa_thuan_trong_tai`; bổ sung typed field tương ứng. Đây là sự kiện/thỏa
  thuận có nguồn, không phải tùy chọn kỹ thuật của backend.
- Mọi scope record có mã contract field chung. Riêng family mẫu NĐ02/2022 được
  ghi rõ điều kiện bên bán kinh doanh và giao dịch KDBĐS, tránh trông chờ một
  party-capacity policy ngầm chưa có cho group đó.

Không sửa profile của 360 hợp đồng để mặc định hai field mới là true/false.
Người 2 phải trích/đối chiếu và cung cấp facts/evidence. Dữ kiện chưa rõ giữ null.

### 2.3. Nguồn chính và bổ trợ

`PV_HYC016` đổi văn bản chính từ mã ghép `VBPL009` về `VBPL008`, điều chính từ
phụ lục danh mục về `ART_VBPL008_19`. Hai criterion của version này vốn đã trỏ
Điều 19, nay không còn bị lệch ownership với primary document.

`nguon_yeu_cau` giữ đầy đủ căn cứ hỗ trợ, phân biệt Điều 19 là nguồn chính và
phụ lục danh mục QĐ02/2012 là nguồn bổ trợ phạm vi; sửa định vị của phụ lục về
đúng mục danh mục. Không xóa mã ghép khỏi dữ liệu lịch sử.

### 2.4. Đóng đúng các dòng chờ duyệt cũ

342 dòng `khoang_trong_tri_thuc` loại HUMAN_APPROVAL vẫn ghi chờ duyệt trong
workbook đầu vào, dù chủ dự án đã xác nhận duyệt knowledge. Đã chuyển chúng sang
`CLOSED_USER_REVIEW_20261105`, ghi rõ cơ sở là xác nhận của chủ dự án.

Điều này không đóng khoảng trống thiếu tiêu chí, thiếu bản luật lịch sử hoặc
checklist NOXH. Revision bổ sung tám gap về khả năng xử lý nguồn đồng thời để
không che vấn đề bằng việc chọn tùy tiện một nguồn.

`phien_ban_trien_khai` thêm pin mới `V750_KNOWLEDGE_ALIGNED_20261106`; dòng pin cũ
giữ nguyên. `nhat_ky_ra_soat` có sự kiện technical alignment mới. Sự kiện do
công cụ tạo không tự ghi là human-reviewed đối với metadata vừa soạn.

## 3. Code/contracts đi kèm đã thay gì?

| Phần | Thay đổi |
|---|---|
| `modules/applicable_law/catalog_policy.py` | Model policy và guard chuyển tiếp có nguồn; không coi thiếu fact là false |
| Temporal resolver | Hiểu markers chuẩn và policy; giữ ngày ký/sự kiện gốc, ghi riêng ngày chọn chế độ khi chuyển tiếp; không chọn một nguồn làm mất nguồn đồng thời chưa phân giải |
| C02 | Thêm hai optional boolean fields; input lịch sử thiếu hai field vẫn đọc được |
| Schemas/catalog/OpenAPI/frontend types | Cập nhật cùng model, không để DTO cho phép field nhưng tài liệu máy đọc từ chối field |
| Dictionary/playbook/hướng dẫn B | Ghi nguồn facts, nơi lưu, trách nhiệm và sự khác nhau giữa bản reviewed cũ/revision mới |
| Tests | Bổ sung ca biên hiệu lực, có/thiếu/mâu thuẫn fact chuyển tiếp, mẫu không có ngày dùng, catalog thiếu criteria và nhiều nguồn đồng thời |

Không viết thay extractor, verifier hoặc thuật toán retrieval của từng người.
Hai field mới dùng cột facts/evidence hiện có khi lưu DB, không tạo thêm cột
profile mà các mapper cũ chưa biết. Mapper đọc DB cần dựng lại typed fields từ
đúng facts/extraction version; không chỉ SELECT `ho_so_hop_dong` rồi mong có giá trị.

## 4. Những phần chưa được coi là đã giải quyết

Có 11 gap OPEN trong workbook mới: tám family có nguồn đồng thời, một thiếu
criteria mẫu NĐ02/2022, một đề xuất bổ sung phiên bản lịch sử tài khoản bảo trì
và một checklist NOXH chuyên biệt. Chi tiết ở `KNOWN_LIMITS.json`.

C05 hiện có một `requirement_version_id` cho mỗi kết quả. Khi hai nguồn/group
cùng điều chỉnh một vấn đề, không được sửa ngày hiệu lực cho hết chồng lấn.
Consumer cần cơ chế tập nguồn hoặc instance theo group trước khi tuyên bố xử lý
đầy đủ. Trong lúc chưa có cơ chế đó, resolver giữ UNKNOWN cho trường hợp chưa
phân giải, kể cả có một group MATCH và group kia chưa rõ.

Các nhánh chuyển tiếp consumer/housing phức tạp vẫn cần hồ sơ và implementation
theo ca. Khai báo mã CONSUMER_80/HOUSING_198 không tự chứng minh mọi nhánh đã chạy.
Nguồn ngày ký có sẵn cũng không thay chứng từ thu tiền, biên bản nghiệm thu hoặc
chứng từ bảo lãnh. Revision không tạo một bản xác nhận pháp lý cho mọi giao dịch.

## 5. Runtime, QA, DB và cách nhóm sử dụng

Tất cả sheets runtime và QA payload giữ nguyên nội dung và checksum XML của bản
đầu vào. `QA_README` có thêm thông báo phiên bản để người đọc không nhầm knowledge
mới với expected cũ. PDFs và URL Supabase được giữ nguyên.

Các workbook đầy đủ mới là **revision tri thức kèm runtime lịch sử**, chưa phải
gói seed/eval mới được chứng nhận tương thích. Không cập nhật manifest tải chung,
không đổi hash trên đáp án cũ, không tự chạy seed/update DB bằng các file này.

Nhóm dùng ngay workbook nhỏ và ma trận để thống nhất implementation:

1. Người 1 giữ các hash/pin và bảng nguồn; cùng người 3/4 đóng các gap thật, soát
   policy theo nguồn, không đổi luật để tránh UNKNOWN.
2. Người 2 cung cấp hai field scope và các mốc/facts có evidence; bổ sung mapper
   đọc/lưu facts nếu cần; không điền ngày thu tiền bằng ngày ký.
3. Người 3 dùng đúng policy khi chạy resolver, nhận diện nguồn đồng thời và
   công bố C04/C05/C06 mới cho phạm vi đã hỗ trợ.
4. Người 4 dùng sự kiện/chứng từ theo từng criterion; không xem C05 RESOLVED là
   bằng chứng đã thực hiện nghĩa vụ hoặc đã đủ verifier.
5. Người 5 pin đúng version/hash cho run mới và truyền C02 đầy đủ; UI phân biệt
   thiếu nguồn, thiếu dữ kiện, giới hạn catalog và lỗi xử lý.

Sau khi các output mới được kiểm chứng, mới phát hành bộ DEV/VALIDATION và TEST
tương thích, cập nhật manifest/Drive và áp dụng DB có kiểm soát. Cluster legal
tiếp tục dừng; revision này chưa được commit/push hoặc triển khai lên cụm.

## 6. Kiểm tra

`VALIDATION.json` ghi kết quả kiểm cả ba workbook: input trùng file trong ZIP
được cung cấp, knowledge hash trùng snapshot mới, đủ 22 bảng tri thức/quản trị,
khóa ngoại knowledge hợp lệ, không chồng khoảng hiệu lực trong cùng group,
mọi policy có schema và article IDs hợp lệ, runtime/QA lịch sử được bảo toàn.

Inventory của revision: **0 marker mapping gaps, 0 unsupported scope fields và
0 direct source ownership mismatches**. Đây là kiểm tra metadata, không phải
metric độ chính xác pháp lý hoặc kết quả chạy đủ 360 PDF với LLM/OCR/verifier.
Kết quả kiểm code được ghi trong `CODE_CHECKS.json` của gói bàn giao ngoài Git.
