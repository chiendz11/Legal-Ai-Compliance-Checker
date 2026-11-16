# Kết quả demo TEAM trên k3d — HD360_001.pdf — 07/11/2026

Đây là run trước khi bổ sung chứng từ synthetic/verifier/batch. Xem
[bản sửa và demo kế tiếp](synthetic_evidence_and_inference_fixes_20261107.md).

## 1. Kết luận có bằng chứng

Đã chuyển k3d sang DB TEAM mới và chạy một PDF thật qua browser → API → Redis →
Celery worker → modules → report. Các boundary validators và source/run/hash checks
đạt trên output thật. Bộ này cải thiện phần phân giải áp dụng so với report cũ,
nhưng compliance vẫn toàn UNKNOWN/INSUFFICIENT do verifier và các vấn đề xử lý nêu
bên dưới. Không gọi đây là nghiệm thu chất lượng pháp lý hoặc customer release.

| Thuộc tính | Giá trị thực tế |
|---|---|
| Cluster/context | legal-checker-local / k3d-legal-checker-local |
| Frontend | http://app.legal-checker.localhost:18880 |
| Dataset | v7.5.0-pdf360-team-baseline-20261107 |
| Knowledge | V750_TEAM_KNOWLEDGE_20261107 |
| Knowledge SHA | 39d823fb72b886d88d55367e928f96a39218d16e4287899fc1a163d25458bc4d |
| Review tri thức | SOURCE_CHECKED, không tự promote HUMAN_VERIFIED |
| DB trong cụm | legal_checker_dev_team_20261107 |
| Case | CA_UP_A1D0EF310159 |
| Run | RUN_1d276b9ca7824a2da554b28c413d5963 |
| Report | REPORT_b435d594-cd06-5e51-b331-a16d483b367c |
| Module source | MODULES; không QA replay/DI reference |
| LLM | gemini-3.5-flash-lite qua endpoint OpenAI-compatible đang cấu hình trong GitOps |
| Queue | celery; API/worker/Beat cùng backend image |
| Báo cáo | DRAFT/PENDING, không tạo human review hoặc publish giả |

API /api/v1/knowledge đọc đúng 323 families, 357 versions, 479 criteria và
SOURCE_CHECKED. SQL schema v7.4.9 không có nghĩa đang chạy knowledge v7.4.9.

## 2. Nguồn đầu vào và cách chạy

Upload HD360_001.pdf thuộc biến thể FULL có sẵn: 75 trang, 595.405 bytes, SHA-256
1f420ef80cc594887c24e82c1f102bbb39423ee98cc394344863c059bb6cde3a. Không sửa PDF để
chạy demo. FULL có nghĩa bộ biến thể điền thông tin, không bảo đảm đầy đủ chứng từ
ngoài hợp đồng hoặc tất cả điều kiện pháp lý trong catalog.

Browser tạo contract/case/run mới, không dùng C02/C07 seed để thay kết quả module.
Mốc intake để null; Documents trích ngày giao kết 2017-02-16 từ nguồn; resolver dùng
mốc theo từng requirement. Không lấy ngày chạy 2026-11-07 làm ngày ký hợp đồng.

Cụm tiếp tục dùng legal-llm-secret hiện có. Key không nằm trong docs, GitOps hoặc
receipts. Một lần GET models chỉ kiểm cấu hình; demo đã có X02 HTTP attempts thật.

## 3. So với report cũ trên đúng cùng PDF

Report cũ: REPORT_a2f6d11e-5b3e-5a0e-9ec0-aafea8d22fd8, case CA_UP_35D196C93AD3,
run RUN_933b9aef1e1f4e47967e6670274955ff, snapshot USER_REVIEWED_20261105. SHA nguồn
khớp byte-for-byte với PDF demo mới.

| Đầu ra | Cũ | TEAM mới |
|---|---:|---:|
| C05 requirements được xét | 306 | 323 |
| CONFIRMED | 41 | 70 |
| NOT_APPLICABLE | 162 | 235 |
| UNKNOWN | 103 | 18 |
| C07 | 76 UNKNOWN | 134 UNKNOWN |
| C08 | 144 INSUFFICIENT | 88 INSUFFICIENT |
| C09 | 5 VALID + 6 UNKNOWN | 5 VALID + 6 UNKNOWN |

Catalog và cách tách source families đã thay đổi; đây không phải metric accuracy
trên gold độc lập. Số C08 giảm chủ yếu liên quan tập yêu cầu còn xét sau loại N/A,
không phải đã biến 56 kết luận thành COMPLIANT. Không có C07/C08 chắc chắn trong
run mới này.

## 4. Kiểm tra điểm nối trên dữ liệu thật

- C02 có 32 facts, 130 chunks và 11 C03; active chunks đã tồn tại trong DB của đúng
  contract trước Retrieval. Có diagnostic DOCUMENT_EXTRACTION_PERSISTED.
- validate_document, validate_legal, validate_retrieval và validate_report đều pass
  bằng DTO thật, Knowledge snapshot đúng hash và nguyên output producer/consumer.
- C10 giữ XOR nguồn C07/C09; C11 trỏ đúng risk instance. Không trộn case/run/hash
  hoặc nguồn PDF khác; 134 verification risks từ criterion và 6 từ citations.
- Run COMPLETED, không error_json, có đúng một initial report. Report giữ nguyên
  profile, requirements, compliance/citation findings và merged risks/recommendations.
- Browser mở đủ 8 tabs; không page error hoặc HTTP error trong lần kiểm tra.
  Khung PDF same-origin trả đúng SHA; export JSON/PDF đều HTTP 200.
- Export JSON là envelope gồm verification và report. Trường report khớp C13 đã
  lưu; muốn đối chiếu report_sha256 dùng report_digest(FinalReport.model_validate(
  export_json['report'])), không hash cả file JSON có stamp như một report object.
- Không tạo C12 review. Tab review chỉ đọc trạng thái; không tự CONFIRM các kết quả.

Các bằng chứng private trong data/private/demo_team_20261107: run_accepted.json,
live_draft.json, live_report.json, live_validation.json, browser_checks.json,
previous_report.json/previous_summary.json, screenshots từng tab và report.pdf/json.
Chúng ngoài Git; các ID trên là run đã kiểm tra trên máy tech lead, không phải IDs
mà tất cả thành viên có sẵn sau seed.

## 5. Vì sao vẫn chưa có kết luận tuân thủ chắc chắn?

### Verifier chưa inject — người 4 cung cấp, người 5 nối

Có diagnostic VERIFICATION_PROVIDER_NOT_CONFIGURED. Với các criterion cần case facts,
local applicability hoặc attestations riêng, LLM quote đúng vẫn chưa đủ. Cổng inject
đã có không có nghĩa implementation verifier đã tồn tại. Không sửa facts_verified/
local_applicability thành true hàng loạt để mở kết luận.

### Budget/provider/quote — người 4 và 5, phối hợp người 3

134 criterion có output, nhưng chỉ 40 criterion được gọi provider theo cấu hình.
Audit ghi 51 attempts: 32 SUCCESS, 18 RATE_LIMIT và 1 TEMPORARY_HTTP_ERROR, có retries.
SUCCESS là thành công transport/audit, không tự chứng minh C07 đã có kết luận đúng.

| Disposition của 134 criterion | Số |
|---|---:|
| CALL_LIMIT, chưa gọi | 88 |
| NO_SELECTED_C06 | 6 |
| RATE_LIMIT cuối cùng | 8 |
| QUOTE_MISMATCH | 11 |
| UNRESOLVED_CONDITIONS | 2 |
| Còn lại có proposal nhưng vẫn thiếu checks để kết luận | 19 |

Tăng budget một mình không giải quyết verifier. Quote mismatch phải sửa evidence/
prompt/adapter theo text nguồn, không bỏ grounding. Retry queue không tự chạy lại
criterion đã được provider bắt lỗi thành diagnostic. Có 140 verification risks và
140 yêu cầu xác minh; đây không phải 140 vi phạm pháp luật đã xác lập.

### Extraction và context còn thiếu — người 2, 3, 4

Trang 17 PDF có câu bảo hành nhà ở 60 tháng, nhưng facts live chưa có warranty_months.
Đây là thiếu extraction/binding, không cần viết thêm PDF. Tiếp tục trích unit, mốc
bắt đầu và evidence; semantic duration không tự chứng minh performance đã thực hiện.

Một số proposals chỉ thấy clause có placeholder trong thân hợp đồng dù có phụ lục
giao dịch. Cần kiểm retrieval/context liên quan và relevance theo criterion, không
coi top-K quote đúng là đã đọc đủ nội dung. Không tự suy phụ lục luôn thắng thân.

Các fields NOXH/điện tử/trọng tài và một số mốc TEMPLATE_USE chưa được nguồn xác nhận;
18 C05 UNKNOWN phải điều tra theo reason của từng requirement. Có version ứng viên
không đồng nghĩa scope/temporal đã đủ. Không mặc định false hoặc dùng ngày ký thay
mọi event.

## 6. Các sửa đổi đã thực hiện trong lượt demo

1. Host .env chuyển workbook/DB/snapshot TEAM; native DB đã seed riêng. Đây không
   phải cùng instance với PostgreSQL k3d.
2. Infrastructure seed gọi app CLI, thêm --database-name, dùng streaming importer,
   init/migrate và manifest pin. K3d seed 531.815 rows; 300 corpus + 32 QA regression.
3. LocalStack database DSN chuyển DB mới, ESO xác nhận; giữ credentials và DB cũ.
4. GitOps pin TEAM hash/deployment/rules và image receipts. Source chưa publish nên
   dùng apply-local, suspend auto-sync đúng hai Legal Applications. Không tuyên bố
   Argo Synced một commit mới; hạ tầng khác không bị thay đổi.
5. Sửa /api/v1/knowledge để SOURCE_CHECKED không bị gộp thành PENDING_HUMAN_REVIEW;
   thêm response model, OpenAPI và 4 regression cases cho các mức review.
6. Report audit lưu knowledge_review_status và FE hiển thị riêng với human review
   của report. Source checked không bị gọi là human approved hoặc legal gold.
7. Header phân biệt mốc intake chưa khai báo với mốc C05 đã phân giải; C08 dùng
   nhãn 'có kết quả bản nháp', không ngụ ý mọi criterion đã được LLM xử lý.

DB cũ trong cụm vẫn có đúng 17 run và 12 report versions trước/sau; DB TEAM có 301
cases sau upload, một run COMPLETED và một report. Các báo cáo cũ không bị viết lại.

## 7. Phạm vi nghiệm thu

Đây là bằng chứng handoff/E2E kỹ thuật trên một PDF thực, có provider thật và output
draft; không phải đánh giá độc lập toàn corpus, hoàn thành verifier hoặc chứng nhận
pháp lý. Phần cần làm tiếp đã có owner, schema và gate trong playbook. Người 1 không
được đóng công việc của người 2–5 chỉ vì pods Ready hoặc docs/schema tests pass.

Kiểm tra cuối: **68 contract/unit tests pass** với PostgreSQL tests được bật; Ruff
và diff checks pass. Frontend build pass, browser mở đủ 8 tab và kiểm lại nhãn
intake/source review/draft coverage, link recommendation → risk → criterion. Không
page error hoặc HTTP error trong các probe. JSON/PDF export HTTP 200; report field
của JSON export khớp report đã lưu. API/worker/Beat đều Ready và dùng cùng image;
hai Argo Applications Healthy nhưng OutOfSync có chủ đích do apply source local,
auto-sync đang tạm dừng. Chưa commit/push hoặc publish images lên registry remote.
