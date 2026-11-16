# Hoàn thiện verifier, evidence và báo cáo HD360_001 — 08/11/2026

## 1. Vấn đề được xử lý

Lượt trước `REPORT_cb032a2e-1057-5f93-9273-ec3ec57c52f4` còn 41 C08 INSUFFICIENT,
59 C07 UNKNOWN (18 criterion được loại theo điều kiện riêng), và bốn
NO_SELECTED_C06. Chạy được pipeline chưa chứng minh từng kết luận đã đủ căn cứ.

Đợt này sửa implementation và kịch bản kiểm thử đã khai báo. Không sửa luật,
workbook TEAM, snapshot tri thức, 360 PDF hoặc các report đã tồn tại. Tiếp tục dùng
PDF HD360_001 synthetic 76 trang; 75 trang nền giữ nguyên, trang 76 là phụ lục đồ án.
Đây là kiểm chứng tích hợp một ca, không phải điểm accuracy trên DEV/VAL/TEST.

## 2. Sửa những gì và vì sao?

### 2.1. Documents: trích thông tin tài khoản bảo trì

`profile_extractor.py` nâng rules-v5, trích literal số tài khoản, tên tài khoản và tổ
chức tín dụng vào `maintenance_account_number`, `maintenance_account_holder`,
`maintenance_bank`. Mỗi fact giữ quote/offset và trạng thái EXTRACTED/CONFLICT.

Trong PDF có TEST-MAINT-001 / TEST-CHU-DAU-TU / TEST-BANK. Đây là giá trị giả lập
được ghi rõ trong nguồn; không phải xác minh một tài khoản ngân hàng thật tồn tại.
Không lấy tài khoản nhận tiền mua căn hộ thay tài khoản bảo trì. Pipeline version
thay đổi nên chunk/fact IDs mới không ghi đè extraction lịch sử.

### 2.2. Retrieval: chọn được dữ liệu đã trích và đúng chủ đề

- Bổ sung cách viết “giá mua bán”, “ngày, tháng, năm ký kết”, “thời điểm có hiệu
  lực”, “thời hạn giao”, “đặc điểm căn hộ” vào mapping facts → query.
- Chọn đa dạng theo field trước khi lấy các lần xuất hiện lặp lại. Ví dụ mã căn hộ
  lặp nhiều lần không chiếm hết chỗ của tầng/tòa và diện tích.
- Topic anchors tìm thời hạn/tiến độ thanh toán, hợp đồng trả dần bằng văn bản,
  hồ sơ bàn giao và đúng tiêu đề quyền/nghĩa vụ bên mua.
- Đây chỉ là candidate evidence. C07 vẫn so predicate và kiểm source/quote; score
  tăng không tự kết luận SATISFIED hoặc biến truy xuất rỗng thành MISSING.

### 2.3. Rà toàn văn để kiểm nội dung cấm hoặc nội dung bắt buộc

`FullDocumentReviewer` đọc toàn bộ active chunks theo batch có một chunk ngữ cảnh
chồng lấn. Mỗi batch phải trả đủ ma trận chunk/criterion. Với PROHIBITED_CLAUSE,
PRESENT nghĩa là thấy hành vi bị cấm, không chỉ thấy một từ khóa. Với nội dung bắt
buộc, placeholder trống không được coi là giá trị đã điền.

Backend chỉ cấp absence_verified khi mọi chunk đã được rà và tất cả batch của
criterion đều ABSENT. Một UNCERTAIN, batch lỗi, alias lạ, bỏ sót chunk/criterion,
hoặc hết ngân sách đều không chứng minh vắng nội dung.

Chứng từ `DocumentReviewArtifact` khóa case/run/contract/knowledge hash, PDF SHA,
extraction version, hash từng chunk, từng batch, model và prompt. JSON lưu bất biến
trên shared PVC tại `evidence/<sha>.json`. Excerpt C07 là literal JSON string ở
`/conclusion_text/<criterion_id>`; không bịa quote cho đoạn không tồn tại.

### 2.4. Evidence được quay lại C06 trước khi C07 đánh giá

Luồng mới:

```text
Documents → lưu extraction → Retrieval ban đầu
                         → verifier + rà toàn văn
                         → trả C06 đã bổ sung active source candidates
                         → validate C06 → C07 → C08 → C10/C11 → C13
```

Port `retrieval_refinement.refine(...)` phải trả danh sách C06 mới. Workflow nhận
lại và validate danh sách đó trước khi gửi cho reasoning. Không sửa riêng một bản
copy của C06 bên trong provider rồi cho rằng evaluator cũng nhìn thấy thay đổi.
Các cặp requirement/criterion, active chunks và run được kiểm trước khi nhận.

Kết quả rà toàn văn đi qua automatic_review, build_verified_observation và reasoner
như các proposal khác. MISSING chỉ cho loại nội dung được hỗ trợ, nội dung bắt
buộc và đầy đủ coverage/absence/related-documents/reliability gates.

Cập nhật vòng tiếp theo: chỉ nhánh ABSENT được admission trực tiếp khi đủ proof.
PRESENT là candidate C06 và phải qua semantic C07; không chỉ dựa vào lượt tìm đoạn
để kết luận vi phạm/đạt. Xem [bản sửa tiếp](complete_runtime_alignment_20261108.md).

### 2.5. Bổ sung attestations synthetic theo từng nghiệp vụ

Scenario `hd360_001.json` khai báo rõ các hồ sơ giả lập về quyền bán tài sản,
chất lượng/loại/số lượng bàn giao, hướng dẫn sử dụng, quyền sở hữu, công khai/niêm
yết điều kiện giao dịch chung và đăng ký/đối chiếu mẫu. Từng claim có criterion,
local applicability, conditions/exceptions và JSON pointer nguồn riêng.

Các nhánh giá Nhà nước, nơi giao mặc định, chi phí mặc định, tranh chấp quyền của
người thứ ba hoặc cá nhân bán quy mô nhỏ được loại chỉ khi điều kiện kịch bản đã
nêu rõ. Không loại tất cả nghĩa vụ bàn giao: đủ số lượng/đúng loại vẫn được đánh giá.
Không dùng chứng từ bên ngoài để khẳng định một nội dung đang trống đã nằm trong
hợp đồng. Mô tả thửa đất được rà từ chính toàn văn.

Trang 25 và 75 đã được nhìn trực tiếp: vùng thực hiện ký vẫn trống. Chứng từ
SOURCE_PINNED_VISUAL_INSPECTION khóa đúng SHA và các trang đó để ghi nhận thiếu nội
dung thực hiện ký. Không tạo chữ ký, dấu hoặc C12 CONFIRM. Kiểm text không tự
chứng nhận một chữ ký/con dấu có thật.

Các revision JSON được lưu theo hash, cùng các biên bản rà. Thay file cấu hình
không làm mất nguồn mà report lịch sử đã dẫn. PDF khác hoặc knowledge hash khác
không nhận các attestations của kịch bản này.

### 2.6. Phân biệt không phát sinh nghĩa vụ với thiếu căn cứ

C08 snapshot thêm `assessment_disposition`:

| Giá trị | Ý nghĩa |
|---|---|
| ASSESSED | Có kết quả đánh giá theo policy |
| NEEDS_EVIDENCE | Còn criterion cần căn cứ/nội dung để kết luận |
| LEGAL_SCOPE_UNRESOLVED | C05 hoặc catalog chưa phân giải được |
| NOT_TRIGGERED | Tất cả criterion bắt buộc đã được loại theo điều kiện riêng, có lý do hợp lệ |

Bốn status pháp lý và AGG_CAN_HO_V1 giữ nguyên. Policy hiện trả INSUFFICIENT khi
không còn criterion bắt buộc áp dụng; không tự đổi thành COMPLIANT. FE giải thích
NOT_TRIGGERED riêng; C13 giữ cả số formal statuses và số operational dispositions.

Tab Tuân thủ phân biệt trích đoạn, biên bản rà toàn văn của máy và chứng từ giả lập.
“Backend đã kiểm tra nguồn/hash” không có nghĩa là con người đã duyệt kết luận.
Báo cáo và export vẫn ghi rõ SYNTHETIC, review_status=PENDING.

Backend còn kiểm chủ thể của evidence: mô tả căn hộ/phần sở hữu chung không thay
cho mô tả thửa đất. PRESENT sai chủ thể được hạ về UNCERTAIN, giữ lý do
SUBJECT_NOT_IN_EVIDENCE trong artifact. `content_subject_validated=False` chặn
provider sau đó tự nâng lại một kết luận chưa có nguồn đúng chủ thể. Kịch bản
HD360_001 giữ cờ này False cho mô tả thửa đất: các vùng chi tiết còn để trống, chưa
có proof đủ để xác nhận predicate; không ép thành MISSING chỉ qua text hoặc hình
sơ đồ chưa được xác minh. Lý do được giữ trong giải thích C07.

## 3. Cấu hình và giới hạn ngân sách

`ASSESSMENT_FULL_DOCUMENT_REVIEW=on` bật lượt rà khi đã có LLM và source cache.
Rà toàn văn và reasoning dùng chung ngân sách ASSESSMENT_LLM_MAX_CALLS, theo đơn vị
criterion analysis. Một criterion trong một batch rà (kể cả repair) tốn một đơn vị;
batch semantic có nhiều criterion vẫn tính từng criterion, không tính là một.
Số HTTP attempts thực có audit riêng, gồm retries của transport.

Tắt rà toàn văn hoặc hết ngân sách không làm absence trở thành đúng. Source-only
vẫn cần verifier nghiệp vụ và chứng từ thật; scenario không phải verifier bao phủ
mọi ca của toàn catalog. Các kết luận máy còn cần nghiệm thu chất lượng riêng.

## 4. Trách nhiệm khi cả nhóm tiếp tục phát triển

| Người | Quy ước đã chốt |
|---|---|
| 1 | Giữ PDF/knowledge/scenario hash tương thích; không đổi source của report lịch sử |
| 2 | C02 facts có source/offset; tài khoản bảo trì tách tài khoản thu tiền |
| 3 | Mapping query → facts và context có relevance; refiner trả C06 hợp lệ |
| 4 | Kiểm từng criterion/ngoại lệ; coverage không thay semantic proof; thiếu thật phải giữ đúng |
| 5 | Compose refiner trước C07, lưu report cùng run; FE phân biệt loại nguồn và disposition |

JSON Schema và ý nghĩa bàn giao được bổ sung tại
[contracts](../contracts/README.md#5-rà-toàn-văn-và-bổ-sung-evidence-cho-c06),
[từ điển](../contracts/data_dictionary.md) và
[hướng dẫn verifier](../modules/criterion_verification_guide.md).

## 5. Kết quả kiểm chứng

Kết quả dưới đây đo trên cùng PDF SHA và knowledge snapshot với lượt baseline.
Source, tests, triển khai k3d, provider thật và nghiệm thu chất lượng là các bằng
chứng khác nhau; đây chưa phải eval pháp lý độc lập.


Lượt cuối dùng **modules thật**, PDF upload và Gemini qua API tương thích OpenAI,
không dùng QA replay:

- Case: `CA_UP_322C5E42E6B1`.
- Run: `RUN_af5f6722174a479abf29edc5b31fb6ee`.
- [Báo cáo cuối](http://app.legal-checker.localhost:18880/reports/REPORT_377287f5-8746-51f4-b0f4-919ae7d083a5?tab=compliance).
- Knowledge: `V750_TEAM_KNOWLEDGE_20261107`, SHA
  `39d823fb72b886d88d55367e928f96a39218d16e4287899fc1a163d25458bc4d`.
- PDF SHA: `c7949fa0075311d280aa455694c637551c6038e4332fb3ffee643b683a4c1ffc`.

| Kết quả | Lượt baseline | Lượt cuối |
|---|---:|---:|
| C07 SATISFIED | 68 | 100 |
| C07 VIOLATED | 2 | 2 |
| C07 MISSING | 0 | 2 |
| C07 UNKNOWN, gồm criterion loại theo điều kiện | 59 | 25 |
| Criterion đã loại có căn cứ trong nhóm UNKNOWN | 18 | 21 |
| C08 COMPLIANT | 35 | 63 |
| C08 NON_COMPLIANT | 2 | 3 |
| C08 INSUFFICIENT theo policy đã pin | 41 | 12 |
| Lỗi NO_SELECTED_C06 | 4 | 0 |

Ba NON_COMPLIANT gồm hai requirement thanh toán có numeric rule không đạt và một
requirement về nội dung thực hiện ký còn thiếu. Hai kết quả MISSING của C07 nằm ở
nhóm ký/đại diện/dấu, dựa trên các vùng ký đã nhìn trực tiếp, không tạo chữ ký mới.

**Đọc đúng 12 INSUFFICIENT:**

- **5 NOT_TRIGGERED**: DS438, DS447, DS448, DS449, DS452. Điều kiện riêng không phát
  sinh; không phải lỗi thiếu hồ sơ. Formal C08 vẫn giữ theo AGG_CAN_HO_V1.
- **3 LEGAL_SCOPE_UNRESOLVED**: FAM_APT_DEPOSIT thiếu marker DEPOSIT_AGREEMENT;
  FAM_GYC048 chưa có coverage catalog tại 10/02/2017; FAM_MAINTENANCE_ACCOUNT chưa
  có coverage tại 16/02/2017 và còn scope chủ thể chưa xác nhận. Không bịa mốc hoặc
  phiên bản lịch sử để đổi nhãn.
- **4 NEEDS_EVIDENCE**: mô tả thửa đất (`TC_PV_HYC040_02`), điều kiện/mốc bắt đầu bảo
  hành (`TC_PV_DS446_02`), cách ghi khoản bảo trì trong hợp đồng
  (`TC_PV_HYC049_01`), địa chỉ các bên (`TC_PV_HYC039_02`).

Kiểm tra lại pre-verification của cả bốn criterion cuối: đều có scenario binding,
local MATCH, source gate, exception checks và legal basis hợp lệ. Đây không phải
VERIFICATION_PROVIDER_NOT_CONFIGURED. Riêng thửa đất có chốt nội dung chưa xác minh;
ba trường hợp còn lại là semantic proposal chưa đủ điều kiện được nhận. Cần đối
chiếu gói C06/annex với đúng predicate; không kết luận mặc định tất cả đều là thông
tin hoàn toàn vắng trong PDF, và không tự đổi mọi UNKNOWN thành SATISFIED.

C09 giữ 5 VALID / 6 UNKNOWN. C10 có 4 compliance risks / 0 citation risks /
10 verification risks; C11 có 14 recommendations. Citation UNKNOWN vẫn có công
việc xác minh riêng. Human review còn PENDING, không tạo C12 CONFIRM/OVERRIDE và
không tự publish.

Kiểm chứng đã hoàn tất:

- Backend PostgreSQL: **1.534 passed, 7 skipped**; lint và format pass.
- Frontend TypeScript/Vite build pass; 8 tab mở thành công, 0 JavaScript/HTTP errors.
- Export JSON, PDF, DOCX trả HTTP 200; source PDF tải đúng SHA.
- 36 HTTP attempts thành công: 8 full-review + 1 full-review repair + 26 semantic +
  1 semantic repair. Không còn CALL_LIMIT, NO_SELECTED_C06 hoặc QUOTE_MISMATCH trong
  diagnostics cuối. Semantic uncertainty được giữ riêng, không gọi là lỗi HTTP.
- Rà đủ 132 active chunks / 76 trang, 8 batch; artifact giữ 19 criterion targets.
- Validate các handoff Documents/Legal/Retrieval/Report, XOR nguồn risk, liên kết
  recommendation → risk, registry/file SHA và active chunk manifest.
- Run COMPLETED cùng một report đầu tiên; 0 review events. DB lịch sử riêng vẫn
  giữ **17 runs / 12 report versions**.
- Đối chiếu code Python trong API/worker/Beat, gồm đường import thật của 11 modules
  thay đổi trọng tâm. API/worker/Beat cùng image backend.

Nguồn kiểm chứng riêng tư ở `data/private/followup_verifier_20261108/final_run/`:
summary, verification_gaps, input/output thật, review artifact, imported module
hashes, ảnh 8 tab, browser checks và exports. Các trial trước được giữ riêng;
không dùng nhãn thử nghiệm cũ làm gold hoặc thay báo cáo cuối.

## 6. Trạng thái triển khai và sử dụng tiếp

Đã triển khai build local trên k3d. Backend image:
`legal-local/backend:image-8384b70e0459a04e62d6f624d180f021816035df2982f4a2fbf4ccbc1ffa9d8b`.
Frontend image:
`legal-local/frontend:image-edf13b656755f5f495e366c0c12a68d671896b05e218c98fa4d76bac017c6ec7`.

Source trên `feat/integration-contract-alignment`, chưa commit/push. Argo auto-sync
của hai Legal applications vẫn tạm dừng cho lượt thử source local; Healthy không
được gọi là đã Synced source mới lên Git. Cluster và port-forward được giữ chạy.

Không cần seed lại DB: không đổi workbook, schema hoặc snapshot tri thức. Người
khác nhận code sau khi được phát hành; chạy source-only với PDF gốc 75 trang không
đồng nghĩa nhận các chứng từ giả lập của PDF 76 trang đã pin. Không áp dụng blanket
verification cho PDF khách hàng khác. Chất lượng toàn catalog cần eval riêng.
