# Dataset PDF360 v4 r2, runtime và knowledge đã duyệt — 10/11/2026

## 1. Phiên bản dùng chung

Dataset mới là `v7.5.0-pdf360-v4r2-runtime-20261110`. PDF nguồn là
`PDF360_DRAFT_GTC_V4_R2_20261110`. Đây là bản thay thế TEAM_BASELINE_20261107 cho
việc bắt đầu DB phát triển mới; giữ DB cũ để đọc lịch sử.

Knowledge dùng phiên bản `V750_KNOWLEDGE_OWNER_APPROVED_20261110`, snapshot:

```text
4ab2d7ea296ea908e25c09fcb6d5f073f1ebe1917678b36390f803b1c725804a
```

Chủ dự án đã yêu cầu coi toàn bộ knowledge được duyệt. Revision này ghi
`human_verified=true` cho 479 criterion, 1.916 decision rules và 9 ngoại lệ;
trạng thái snapshot là `HUMAN_VERIFIED`. Đồng bộ thêm trạng thái duyệt của
1 văn bản, 24 điều khoản, 14 phiên bản yêu cầu, 102 risk rules và 102 mẫu ở mỗi
catalog risk/recommendation đang ở SOURCE_CHECKED. Các rule chủ động tắt vẫn
giữ tắt, còn metadata hiệu lực hoặc yêu cầu xác minh theo từng giao dịch không
được đổi thành một kết luận pháp lý chung. Có receipt `KNOWLEDGE_ACCEPTANCE.json`
và dòng `knowledge.duyet_tri_thuc` gắn với đúng hash. Đây là quyết định phê duyệt
của chủ dự án theo chỉ thị, không gán một buổi kiểm tra độc lập cho người chưa
thực hiện. Các bản ghi lịch sử vẫn mô tả revision trước của chúng.

Quyết định này áp dụng cho knowledge. Kết quả extraction mới, đề xuất LLM,
review và publish báo cáo vẫn có trạng thái riêng.

## 2. PDF, workbook và các gói khác nhau như thế nào?

90 họ mẫu gốc tạo ra 360 PDF, mỗi họ có bốn biến thể. Chia split theo **họ nguồn**:
biến thể của một mẫu không xuất hiện đồng thời ở DEV và TEST.

| Gói | Nội dung | Người dùng |
| --- | --- | --- |
| MASTER | 360 PDF, runtime/QA đầy đủ và 32 ca rule regression | Tech lead/evaluator |
| DEV_VALIDATION | 240 DEV + 60 VALIDATION, runtime/QA tương ứng và 32 regression | Năm người seed DB local để phát triển |
| TEST_INPUTS | 60 PDF, C01 intake và knowledge dùng chung; không có output/đáp án | Chạy đánh giá giữ kín |

Tên workbook đầy đủ dùng seed:
`bang_du_lieu_v7_5_0_PDF360_V4R2_20261110_DEV_VALIDATION.xlsx`.
Giữ nguyên 50 bảng nghiệp vụ và 6 bảng QA. Không dùng workbook rà soát nhỏ hoặc
workbook đã được Google Sheets chuyển đổi để seed. Các output dài nằm trong
`QA_ARTIFACTS` dạng multipart; phải ghép theo case/role/contract/record rồi kiểm hash.

PDF trong release được đóng kèm dưới `sources/pdf/HD360_*.pdf`. URI trong DB là
`dataset://V750_PDF360_V4R2_20261110/sources/pdf/HD360_001.pdf`, không trỏ lại
URL Supabase cũ chứa PDF v2. `SOURCE_FILES.json` ghi hash từng PDF. Khi chưa xuất
bản v4 r2 lên Supabase, chạy `cache-sources` để bộ đọc nguồn dùng cache theo hash.
API và worker cần cùng nhìn thấy cache này khi chạy nhiều tiến trình/container.

## 3. Phần nào là đáp án kiểm chứng được, phần nào mới là reference?

Có ba lớp cần đọc đúng:

1. **Knowledge đã được chủ dự án duyệt:** luật, phiên bản, criterion và rules
   dùng cùng một immutable snapshot. Không tự đổi ngưỡng hoặc ngày hiệu lực để
   ép nhãn baseline.
2. **Đối chiếu literal độc lập từ nguồn:** `ExtractionReference` và
   `LITERAL_ASSERTIONS.csv` ghi 36 trường trên mỗi PDF. Bộ đối chiếu dùng PyMuPDF,
   khác production extractor dùng pypdf/rules-v10. Gồm giá trị, quote, trang và
   hash PDF. Phạm vi là phụ lục giao dịch synthetic; chưa phải nhãn pháp lý toàn
   bộ tài liệu. Tổng MASTER có 12.960 mục: 12.625 có giá trị nguồn, 245 được cố
   tình bỏ trong phụ lục và 90 mục giá bán mâu thuẫn.
3. **Reference pipeline:** C02–C13 được chạy lại bằng implementation hiện tại,
   không tái dùng chunks/offset/kết quả PDF cũ. Đây là `SILVER_GUARD_REFERENCE`,
   hữu ích để dựng input, kiểm schema/JOIN và regression. Không lấy output của
   engine làm gold để công bố accuracy cho chính engine đó.

Việc một trường bị bỏ trong phụ lục không chứng minh nó vắng ở mọi trang thân
hợp đồng. Bản ghi `WITHHELD_IN_AUTHORED_APPENDIX` giữ giới hạn này. Nhóm mâu thuẫn
cần giữ cả hai giá trị cùng nguồn; không tự chọn một giá để làm đẹp dữ liệu.

Release dựng reference **offline, không gọi LLM mới**. Các tiêu chí chưa có bộ
xác minh nội dung độc lập được giữ UNKNOWN. Bởi vậy phân phối C07/C08 trong
workbook này không tương đương báo cáo demo đã gọi LLM trên HD360_001. Không
chạy chế độ `reference` rồi hiểu đó là chất lượng inference hiện tại.

32 regression có expected assertions viết trước và được kiểm riêng. Chúng kiểm
rules/gates; không thay cho bộ nhãn pháp lý độc lập trên 360 PDF.

## 4. Mỗi người dùng dữ liệu như thế nào?

| Người | Input tham chiếu | Kiểm tra |
| --- | --- | --- |
| 1 — Dataset/DB | Snapshot, source index, schema và toàn bộ QA | Hash, split theo họ, PK/FK, lineage và phát hành |
| 2 — Documents | C01 + bytes PDF đã kiểm hash | So trường được hỗ trợ với literal reference; kiểm quote/page; không chấm giống hệt chunk ID là accuracy |
| 3 — Applicable law/citations/retrieval | C02/C03 upstream, catalog và chunks | C04/C05 theo profile/mốc; citation occurrences; relevance của C06 cần nhãn riêng |
| 4 — Compliance/risk/recommendation | C05/C06/C09 + knowledge cùng hash | Regression độc lập; C07 phải có evidence và verification; reference SILVER chưa phải nhãn legal gold |
| 5 — Workflow/UI/report | Các DTO bàn giao và C13 draft | Đúng case/run/hash, DRAFT_REVIEW, tiến độ, review/publish và export |

C05 hiện xét toàn catalog 323 families, thay vì chỉ 36 families tham chiếu của
release cũ. Không phải tất cả family đều áp dụng cho mọi PDF. Thiếu ngày hoặc
facts vẫn phải trả UNKNOWN đúng nghĩa. Thực hiện JOIN theo
[playbook](parallel_development_playbook.md) và [hướng dẫn sau seed](../modules/README.md).

Đánh giá rule extraction ban đầu trên literal reference có 9.694 mục khớp,
3.021 khác và 245 chưa chấm. Tập 36 trường gồm cả trường production extractor
chưa hỗ trợ; đây không phải precision/recall toàn tài liệu và chưa phải kết quả
so sánh rule với LLM. Khi thử LLM, giữ nguyên tập input/reference/split và báo
metric theo trường, lỗi thiếu, xung đột, quote grounding và chi phí.

## 5. Cài vào máy thành viên

Chạy tại root repo, trong `.venv` đã cài `backend[dev,dataset]`. Nếu chưa có môi
trường, làm theo [dev setup](dev_setup.md). Release local có ZIP tại thư mục:

```text
/home/chienqt/Downloads/legal_compliance_v750_pdf360_v4r2_runtime_20261110/
```

Manifest hiện `LOCAL_ARCHIVE_READY`: chưa trỏ checksum mới vào một link Drive cũ.
Tech lead bàn giao đúng ZIP sau, hoặc upload chính ZIP đó rồi cập nhật URL và
publication status theo bytes thực tế:

```text
legal_compliance_v750_PDF360_V4R2_20261110_DEV_VALIDATION.zip
```

Giữ `.env` riêng, đổi các biến sau sang DB **mới**:

```dotenv
DATABASE_URL=postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_dev_pdfv4r2_20261110
SEED_WORKBOOK_PATH=data/private/v750_pdf360_v4r2_runtime_20261110/bang_du_lieu_v7_5_0_PDF360_V4R2_20261110_DEV_VALIDATION.xlsx
KNOWLEDGE_SNAPSHOT_SHA256=4ab2d7ea296ea908e25c09fcb6d5f073f1ebe1917678b36390f803b1c725804a
DEPLOYMENT_LEGAL_KNOWLEDGE_VERSION=V750_KNOWLEDGE_OWNER_APPROVED_20261110
SOURCE_CACHE_DIR=data/private/source_cache
```

Không chép đè `.env` có key/cấu hình riêng. Với PostgreSQL native hoặc port khác,
giữ credentials/port của máy và chỉ đổi tên database.

```bash
python -m scripts.dataset pull --archive /path/to/legal_compliance_v750_PDF360_V4R2_20261110_DEV_VALIDATION.zip
python -m scripts.dataset check
python -m scripts.dataset cache-sources

docker compose up -d --wait postgres
python -m scripts.local_db init
python -m scripts.local_db seed
python -m scripts.local_db check
```

- `pull`: kiểm ZIP và SHA-256 từng file, cài vào folder mới; không sửa DB.
- `cache-sources`: kiểm index và PDF, chép vào cache theo hash; không sửa DB.
- `init`: tạo DB mới nếu chưa có và chạy Alembic.
- `seed`: nhập workbook và pin knowledge; receipt trong `profile_snapshot_json`
  được khôi phục thành `review_mode=DRAFT_REVIEW`, tránh mặc định nhầm sang
  FULL_ASSESSMENT vì schema workbook cũ chưa có cột này.
- `check`: kiểm dữ liệu đã nhập. Seed lại đúng workbook là idempotent; workbook
  khác checksum bị từ chối để bảo vệ dữ liệu phát triển.

Không dùng lệnh `update` reviewed-flags cho release đổi PDF/chunks này. Giữ DB
và folder cũ. Không cần chạy `align-runtime`/`align-content-defaults` trên release
mới vì các thay đổi catalog đã có sẵn trong snapshot đã pin.

## 6. Đã thay gì trong ứng dụng local?

DB ứng dụng đang chạy đã nhận snapshot knowledge được duyệt. API/worker/scheduler
đã chuyển sang pin mới; API `/api/v1/knowledge` trả `HUMAN_VERIFIED`. Không đổi pin
của case/run cũ, không sửa nội dung 28 báo cáo lịch sử. Đây là rollout local;
chưa phải commit/push, publish GHCR hay Argo sync từ Git.

Workbook reference mới được seed nghiệm thu vào **DB riêng**, không ghi đè runtime
ứng dụng đang demo. Dữ liệu QA của release là tham chiếu cho phát triển; ứng dụng
thật vẫn đọc PDF và chạy module, không âm thầm lấy expected output thay inference.

## 7. Kết quả nghiệm thu release này

Các kiểm tra sau đã thực hiện trên file xuất ra và DB riêng, không chỉ kiểm mẫu JSON:

| Kiểm tra | Kết quả |
| --- | --- |
| MASTER | PASS; 360 ca corpus + 32 regression; 6.182 payload; kiểm 3.081.493 liên kết FK và 30.249 quote/offset SQL |
| DEV_VALIDATION | PASS; 240 DEV + 60 VALIDATION + 32 regression; 5.162 payload; 40.461 C07 khớp giữa QA và SQL |
| TEST_INPUTS | PASS; 60 intake; không có profile, chunks, assertions hay output tham chiếu |
| Seed DB riêng | PASS; 1.471.740 dòng; 300 ca được khôi phục DRAFT_REVIEW; 332 QA cases; không có nhãn TEST |
| Seed lặp lại | `already_seeded`, không nhập trùng |
| JOIN Retrieval | Không có evidence thuộc hợp đồng khác |
| Replay | CA360_001–004 khớp payload tham chiếu; kiểm plumbing/regression, không phải metric legal gold |
| Cài ZIP và cache | 323 file được kiểm hash; 300 PDF cache thành công; đọc lại bốn nguồn qua shared storage |
| Backend | 1.692 passed, 7 skipped; Ruff lint/format và git diff check đạt |

DB nghiệm thu là `legal_checker_test_pdfv4r2_20261110`, khoảng 4,9 GiB sau seed.
Các máy phát triển có thể đặt tên DB riêng theo `.env.example`; không mặc định
chuyển ứng dụng đang demo sang DB nghiệm thu. Case/run/report lịch sử của ứng dụng
vẫn nằm ở DB đang dùng trước đó; knowledge hiện hành của ứng dụng đã được cập nhật.

Các file bàn giao nằm tại:

```text
/home/chienqt/Downloads/legal_compliance_v750_pdf360_v4r2_runtime_20261110/
├── KNOWLEDGE_OWNER_APPROVED_20261110.xlsx
├── bang_du_lieu_v7_5_0_PDF360_V4R2_20261110_MASTER.xlsx
├── bang_du_lieu_v7_5_0_PDF360_V4R2_20261110_DEV_VALIDATION.xlsx
├── bang_du_lieu_v7_5_0_PDF360_V4R2_20261110_TEST_INPUTS.xlsx
├── legal_compliance_v750_PDF360_V4R2_20261110_MASTER.zip
├── legal_compliance_v750_PDF360_V4R2_20261110_DEV_VALIDATION.zip
├── legal_compliance_v750_PDF360_V4R2_20261110_TEST_INPUTS.zip
├── KNOWLEDGE_ACCEPTANCE.json
├── VALIDATION.json
├── SEED_QUALIFICATION.json
├── INSTALL_QUALIFICATION.json
└── CLI_QUALIFICATION.json
```

ZIP MASTER khoảng **1,62 GB**, DEV_VALIDATION **1,36 GB**, TEST_INPUTS **40 MB**.
Workbook knowledge riêng khoảng **1,8 MiB**, phục vụ đọc và rà tri thức; không seed
riêng file này. Full workbook giữ payload dài nên lớn: seeder dùng streaming để
không nạp toàn bộ vào RAM. Không upload full workbook qua Google Sheets rồi dùng
bản được chuyển đổi để seed; checksum và định dạng inline strings sẽ khác.

Manifest đã pin đúng ZIP/file/hash mới nhưng URL còn trống (`LOCAL_ARCHIVE_READY`).
Các ZIP này chưa được upload lên Drive/Supabase. Khi upload, dùng đúng ZIP
DEV_VALIDATION, sau đó cập nhật URL/publication status theo bytes đã kiểm; không
đổi sang link gói nguồn v4 r2 trước đây vì gói đó không có runtime/QA đầy đủ.
