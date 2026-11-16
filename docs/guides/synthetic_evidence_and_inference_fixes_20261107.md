# Chứng từ synthetic và sửa luồng inference — 07/11/2026

## 1. Phạm vi của thay đổi

Theo yêu cầu tech lead, demo đồ án được bổ sung dữ kiện/chứng từ hư cấu khi nguồn
hợp đồng chưa có đủ. Đây là **đầu vào kịch bản synthetic**, không phải văn bản do
ngân hàng, cơ quan nhà nước hoặc khách hàng thật cung cấp. Không tạo chữ ký/con dấu.
Không sửa luật, mốc hiệu lực hoặc kết luận pháp lý để buộc mọi ca đạt COMPLIANT.

Bộ TEAM, workbook, snapshot tri thức và các report lịch sử vẫn giữ nguyên. Lượt này
chạy thêm một bản HD360_001 có phụ lục synthetic. Không cập nhật 360 PDF hay phát hành
lại DEV/VAL/TEST; kết quả demo bổ sung không phải gold để tính metric độc lập.

## 2. Tài liệu và nguồn bổ sung

PDF nền 75 trang được giữ nguyên các trang. Nối thêm một trang cuối có tiêu đề
“PHỤ LỤC DỮ KIỆN VÀ CHỨNG TỪ SYNTHETIC - ĐỒ ÁN SINH VIÊN”, tạo PDF 76 trang.

Các trường bổ sung: không NOXH, bên bán trong nước, giao dịch không điện tử, không
thỏa thuận trọng tài, hợp đồng theo mẫu; ngày hiệu lực, ngày dùng mẫu, ngày thu tiền,
thu tiền trước bàn giao và trước cấp chứng nhận. Ngày ký gốc 16/02/2017 giữ nguyên.

Các chứng từ giả lập gồm hồ sơ dự án/đất/giấy phép/nghiệm thu phần móng, thông báo
và phản hồi đủ điều kiện bán, bảo lãnh/giao bản sao, nhật ký nghiên cứu/lưu/cấp lại
hợp đồng, biên nhận thanh toán. Nội dung từng chứng từ được ghi rõ là SYNTHETIC.

Hai biên nhận cố tình ghi 75% trước bàn giao và 98% trước cấp chứng nhận, để engine
có dữ kiện đối chiếu ngưỡng trong rule lịch sử. Số tiền là dữ kiện kịch bản; nhãn
SATISFIED/VIOLATED vẫn phải do proposal + gate + numeric engine quyết định.

Cấu hình:
`backend/src/legal_checker/modules/compliance/scenarios/hd360_001.json`.
Cấu hình có SHA PDF đích, SHA PDF nền, SHA knowledge và từng criterion attestation.
Chứng từ ngoài đăng ký bằng hash **chính bytes JSON này** và JSON pointer đến excerpt.
Chúng không được giả thành URL công khai hay tài liệu chính thức có thực.

## 3. Nối verifier đúng vào workflow

Composition root tự inject `SourceFactVerifier` cho modules mode. Verifier kiểm
quote/offset thuộc active chunks của C02 và chỉ nhận facts trạng thái EXTRACTED,
có evidence đầy đủ, không lấy CONFLICT hoặc giá trị chưa có chứng minh.
Nó không tự xác nhận nguồn luật, mọi ngoại lệ, local applicability hoặc absence.

Khi có `SYNTHETIC_SCENARIO_PATH`, dùng `SyntheticScenarioEvidence`. Provider chỉ bổ
sung attestations nếu **source SHA và knowledge SHA đều khớp**; file scenario thay
đổi sau khởi tạo sẽ bị từ chối. PDF khác vẫn chỉ đi qua kiểm tra source thông thường.
Không suy chế độ synthetic chỉ từ tên file, tenant hoặc nhãn FULL.

Registry được lọc theo các cặp requirement instance/criterion thực trong C05, trước
khi gửi tới C07. Excerpt và registration cùng SHA, ID và đúng case/run/contract.
Một nguồn giả lập dùng lại cho nhiều criterion có binding riêng; không lấy chứng
từ của criterion A để làm proof cho B.

Backend review có thể nhận các checks synthetic đã khai báo cho criterion đó,
để xét bản nháp dù snapshot mới mang SOURCE_CHECKED. Điều này không đổi cờ
human_verified của knowledge hoặc C02, không tạo C12 CONFIRM và không tự publish.

Không đặt absence_verified/coverage_complete chỉ vì đọc được mọi trang. Vì vậy
các kết luận “không có điều khoản cấm” hoặc MISSING vẫn cần proof riêng; kịch bản
này không cấp blanket absence approval.

## 4. Sửa Document Intelligence và Retrieval

Extractor rules-v4 bổ sung:

- `warranty_months`, `warranty_unit=MONTH`, mốc bắt đầu bảo hành nếu có câu nguồn;
  đọc được câu nối dòng. Nhiều thời hạn khác nhau vẫn là CONFLICT.
- Boolean profile từ nhãn ghi rõ Có/Không; không mặc định False khi không có nhãn.
- COLLECTION, PRE_HANDOVER_COLLECTION, PRE_CERTIFICATE_COLLECTION và TEMPLATE_USE
  từ nhãn sự kiện riêng; không lấy ngày ký thay cho ngày thực thu.
- Facts và evidence vẫn giữ quote/offset trên đúng chunk, human_verified=False.

Retrieval nhận các alias đã thống nhất: gia_ban → gia_tri_hop_dong,
dien_tich → dien_tich_thong_thuy; bỏ prefix profile. khi tìm evidence từ C02.
Không tự chọn mọi chunk hoặc bỏ gate relevance để có metric đẹp.

## 5. Sửa gọi model, quote và ngân sách

`LLMObservationProvider` hỗ trợ batch 1–8 criterion/request, mặc định 1 để giữ tương
thích. Mỗi gói vẫn có C05/C06/rules/facts của riêng criterion. Response phải có đúng
IDs được yêu cầu, không trùng/ngoại lai; từng proposal vẫn validate riêng.

`ASSESSMENT_LLM_MAX_CALLS` tính **số criterion** được cấp ngân sách, không phải số HTTP
requests. Local demo đặt 512 thay 40, batch size 4. `OpenAIResponsesClient` có pacing
10 giây giữa các HTTP attempts; retry transient có giới hạn, giữ audit từng attempt.
Client đọc cả HTTP Retry-After và google.rpc.RetryInfo.retryDelay; khi có 429 sẽ chờ
cooldown, không retry liên tục trong cùng cửa sổ. Không nói đã giải quyết hết 429
nếu tài khoản/provider thật vẫn hết quota.

Prompt `C07_SEMANTIC_V3` cung cấp `quote_catalog`. Model ưu tiên trả quote_id;
backend phục hồi quote/offset từ text gốc, không chép lại đoạn model tự viết.
Response batch dùng item_id C1/C2, quote_ids Q1/Q2 và external_ids E1/E2; server phục hồi doan_id,
text và offset, model không phải chép các IDs dài. IDs thật chỉ do server ánh xạ từ input đã pin.
Nếu response sai IDs/schema, workflow thử lại riêng criterion bị lỗi tối đa một
lần; audit prompt_version có hậu tố _REPAIR. Sai tiếp vẫn UNKNOWN, không sửa quote
để hợp thức hóa. Ngân sách criterion không bị tính trùng; HTTP attempts vẫn audit đủ. Gói model đã bỏ metadata lặp
(scope snapshots/review logs) nhưng giữ rule/predicate/source material cần thiết.
Các numeric predicates có facts và binding đã xác minh được backend tính bằng
Decimal trước khi gọi model; origin NO_CALL, model_version BACKEND_NUMERIC_V1, không
tạo audit HTTP giả. Chỉ các semantic predicates còn lại được đưa vào batch.

Adapter còn chấp nhận khác biệt chỉ ở whitespace khi ánh xạ được duy nhất về nguồn,
rồi lưu lại nguyên văn gốc. Paraphrase, quote ID lạ, evidence chéo criterion hoặc
có nhiều vị trí không phân biệt được vẫn bị từ chối.

## 6. Cấu hình sử dụng

Local host hoặc worker có thể cấu hình:

```dotenv
ASSESSMENT_MODULES=modules
ASSESSMENT_LLM=openai
ASSESSMENT_LLM_MAX_CALLS=512
ASSESSMENT_LLM_BATCH_SIZE=4
C07_LLM_MIN_REQUEST_INTERVAL_SECONDS=10
C07_LLM_MAX_OUTPUT_TOKENS=8192
C07_LLM_MAX_ATTEMPTS=4
C07_LLM_MAX_RETRY_DELAY_SECONDS=90
C07_LLM_TOTAL_TIMEOUT_SECONDS=300
SYNTHETIC_SCENARIO_PATH=backend/src/legal_checker/modules/compliance/scenarios/hd360_001.json
```

Trong Docker path scenario là
`/workspace/backend/src/legal_checker/modules/compliance/scenarios/hd360_001.json`.
API/worker dùng chung image/config. K3d tiếp tục dùng legal-llm-secret có sẵn; key
không nằm trong file scenario, docs hoặc GitOps. Bỏ SYNTHETIC_SCENARIO_PATH khi chạy
source-only. Không cần seed lại DB vì lượt này không đổi schema/workbook/snapshot.

## 7. FE, báo cáo và trách nhiệm năm người

Audit lưu evidence_mode=SYNTHETIC và diagnostic gồm scenario/source SHA. FE có nhãn
chế độ đồ án; PDF/DOCX/JSON export giữ dấu nhận diện synthetic. MODULES vẫn có nghĩa
parser và các module chạy thật, khác QA replay; một run MODULES có thể dùng nguồn
synthetic được khai báo rõ.

| Người | Phần được bổ sung | Việc tiếp tục theo dữ liệu thật |
|---|---|---|
| 1 | Kịch bản/source hash và cấu hình demo | Quản lý release; không trộn demo này vào expected TEST |
| 2 | Facts bảo hành, flags tường minh, event markers | Tiếp tục đo extraction trên corpus, OCR/DOCX theo phạm vi |
| 3 | Alias facts để Retrieval tận dụng đúng C02 | Xử lý khoảng trống lịch sử và đánh giá relevance |
| 4 | Source verifier, scenario verifier, batch/quote checks | Binding/verification thật theo criterion ngoài scenario |
| 5 | Composition, registry filter, audit/FE/export | E2E và cách người dùng bổ sung chứng từ thật |

## 8. Kết quả kiểm chứng

Unit/contract ban đầu: 1.276 passed, 25 skipped do thiếu optional dependencies hoặc
chưa khai báo TEST_DATABASE_URL. Bộ integration PostgreSQL riêng cho assessment runs và document intelligence: **25 passed**,
dùng DB test tạm và đã tự xóa sau kiểm tra. Kết quả demo k3d được bổ sung sau khi
run hoàn tất. Trạng thái pod Ready không thay kết quả kiểm tra output/report.

Kiểm tra toàn backend với PostgreSQL đã chạy 1.500 passed, 7 skipped trước phần
repair. Test app_factory đã được tách khỏi snapshot/LLM/queue trong .env cá nhân;
DB test không còn vô tình đòi snapshot TEAM của DB dev. Các lần chạy test tiếp
theo và kết quả demo cuối được ghi ở phần kết quả bên dưới.

## 9. Kết quả cuối trên k3d ngày 08/11/2026

Frontend: http://app.legal-checker.localhost:18880

Báo cáo cuối:
http://app.legal-checker.localhost:18880/reports/REPORT_cb032a2e-1057-5f93-9273-ec3ec57c52f4

- Case: CA_UP_15AEC8AAC89C.
- Run: RUN_81e17dfb052442a783fc0a92c1cde6c7; COMPLETED, không error_json.
- Dataset: v7.5.0-pdf360-team-baseline-20261107.
- Knowledge: V750_TEAM_KNOWLEDGE_20261107 / SOURCE_CHECKED; SHA
  39d823fb72b886d88d55367e928f96a39218d16e4287899fc1a163d25458bc4d.
- PDF: HD360_001_SYNTHETIC.pdf, 76 trang; SHA
  c7949fa0075311d280aa455694c637551c6038e4332fb3ffee643b683a4c1ffc.
- Mode: MODULES + evidence_mode SYNTHETIC; parser/engines/LLM thật, không QA replay.
- LLM: gemini-3.5-flash-lite qua Secret hiện có; Celery/Redis trên k3d.

So với run TEAM đầu tiên trên PDF chưa bổ sung (khác input vì có thêm phụ lục):

| Đầu ra | TEAM trước bổ sung | Sau sửa + nguồn synthetic |
|---|---:|---:|
| C05 CONFIRMED | 70 | 75 |
| C05 NOT_APPLICABLE | 235 | 245 |
| C05 UNKNOWN | 18 | 3 |
| C07 SATISFIED | 0 | 68 |
| C07 VIOLATED | 0 | 2 |
| C07 UNKNOWN, gồm local exclusions | 134 | 59 |
| C08 COMPLIANT | 0 | 35 |
| C08 NON_COMPLIANT | 0 | 2 |
| C08 INSUFFICIENT | 88 | 41 |
| C09 VALID / UNKNOWN | 5 / 6 | 5 / 6 |

59 C07 UNKNOWN gồm 18 criterion được excluded theo điều kiện của kịch bản; còn 41
criterion chưa có kết luận chắc chắn. Không gọi bảng này là accuracy improvement:
nguồn giả lập đã bổ sung facts, scope thay đổi và expected chưa được đánh giá độc lập.

Hai vi phạm từ biên nhận giả lập được backend tính bằng Decimal:

- TC_PV_HYC036_01: 1.497.600.000 / 1.996.800.000 = 75%, vượt ngưỡng 70% của rule đã pin.
- TC_PV_HYC037_01: 1.956.864.000 / 1.996.800.000 = 98%, vượt ngưỡng 95% của rule đã pin.

TC_PV_HYC034_01 về đợt thu đầu, TC_PV_HYC049_02 về tỷ lệ bảo trì và
TC_PV_HYC053_01 về thời hạn bảo hành cũng đi qua BACKEND_NUMERIC_V1. Tổng 5 criterion
được xử lý số học không gọi model. 120 criterion còn lại có proposal từ Gemini;
4 criterion không có C06 selected nên được giữ UNKNOWN, không bịa một lời gọi AI.

Audit ghi **30 HTTP calls theo lô + 2 calls sửa response riêng**, tất cả SUCCESS.
Hai response ban đầu cần sửa đã được phục hồi; diagnostics cuối không còn
VERIFICATION_PROVIDER_NOT_CONFIGURED, CALL_LIMIT, RATE_LIMIT, QUOTE_MISMATCH,
FOREIGN_QUOTE_ID, FOREIGN_EVIDENCE, FOREIGN_FACT_EVIDENCE, UNREGISTERED_EXTERNAL_ID,
INVALID_SCHEMA hoặc INVALID_BATCH_RESPONSE. Có 2 compliance risks, 47 verification
risks và 49 recommendations; 47 verification risks không phải 47 vi phạm.

### Những trường hợp còn chưa kết luận được

Không coi mọi UNKNOWN là lỗi ghép module. Tuy vậy, các điểm dưới đây vẫn cần hoàn
thiện khi mở rộng phạm vi nghiệp vụ; gói sửa này chưa làm xong toàn bộ verifier cho
mọi criterion của catalog:

1. C05 còn FAM_APT_DEPOSIT thiếu mốc DEPOSIT_AGREEMENT; FAM_GYC048 và
   FAM_MAINTENANCE_ACCOUNT thiếu coverage lịch sử phù hợp. Không tự bịa luật lịch sử.
2. C06 chưa chọn được evidence cho TC_PV_DS433_02, TC_PV_DS434_02,
   TC_PV_DS453_01, TC_PV_HYC015_03. Người 3 cần kiểm relevance/binding theo nội dung;
   không coi empty retrieval là MISSING.
3. Một số criterion còn local applicability/exception checks riêng chưa được
   attestation trong scenario; cần binding nghiệp vụ của người 4 và nguồn phù hợp.
4. Kết luận không có điều khoản cấm/MISSING cần đủ proof về toàn bộ tài liệu.
   Không bật absence_verified chỉ vì hợp đồng thuộc biến thể FULL.
5. Một số placeholder/nội dung hợp đồng và các viện dẫn vẫn chưa đủ rõ. Việc có
   nguồn synthetic không tự giải thích hoặc sửa mọi điều khoản của PDF nền.

Các trường hợp này vẫn xuất hiện rõ trong report thay vì bị đổi sang COMPLIANT.
Phạm vi hoàn tất của lượt này là nguồn synthetic có truy vết, điểm nối verifier,
extraction bảo hành, xử lý số học, gọi model/response validation và demo tích hợp.

### Kiểm chứng cuối

- Toàn backend: **1.502 passed, 7 skipped** với PostgreSQL tests bật. Ruff và
  format checks của các file thay đổi đạt; contract/link checks đạt.
- So hash 12 file runtime trong worker với code local: khớp, gồm adapter/verifier,
  extractor, composition, transport và report/export. API/worker/Beat cùng image.
- validate_document, validate_legal, validate_retrieval, validate_report đều đạt trên
  DTO thật; external source/hash registry, risk provenance và recommendation links đạt.
- 132 active chunks đã được lưu trước Retrieval; đúng một initial report của run;
  không tạo C12 review. DB cũ còn nguyên 17 runs / 12 report versions.
- So sánh content streams và page geometry của 75 trang gốc: không đổi; chỉ thêm
  trang phụ lục số 76. Đã render và xem trực quan trang phụ lục.
- Browser mở đủ 8 tab, không page/HTTP error. Xem PDF nguồn và export JSON/PDF đạt.
  Các kiểm tra navigation, DOCX và stamp được lưu cùng evidence private.

Artifacts trên máy tech lead, ngoài Git:

```text
data/private/demo_synthetic_fixes_20261107/
├── HD360_001_SYNTHETIC.pdf
├── HD360_001_SYNTHETIC_ANNEX.pdf
├── full-backend-tests-verified.log
└── verified_run/
    ├── current_summary.json
    ├── live_validation.json
    ├── runtime_code_hashes.json
    ├── source_preservation.json
    ├── browser_checks.json
    ├── final_browser_checks.json
    ├── report.json / report.pdf / report.docx
    └── ảnh các tab / synthetic-annex-preview.png
```

Nếu chạy lại kịch bản, upload **HD360_001_SYNTHETIC.pdf** ở trên; source/hash guard
không áp các giả định này cho PDF gốc 75 trang hay một hợp đồng khác. Workbook và
360 PDF baseline giữ nguyên, **không cần seed lại DB** để dùng gói sửa code này.

Cụm đang dùng image local build/import; Argo auto-sync tạm dừng trên đúng hai Legal
Applications. Chưa commit/push/publish remote, không gọi trạng thái này là Argo đã
Synced một commit mới. GitOps release metadata ghi đúng image và run demo hiện tại.

Kiểm tra cuối browser đã đạt: nhãn synthetic, risk → criterion và recommendation →
risk mở đúng focus, audit ghi đúng mode, JSON export khớp C13 đã lưu và stamp có
SYNTHETIC; DOCX export HTTP 200. Không page error. Sau khi khởi động lại k3d, đã
khôi phục LocalStack Secrets Manager từ các Secret đang hoạt động; database/Redis/LLM
ExternalSecrets đều Ready/SecretSynced. Không thay key, password hoặc seed lại DB.


Bản tiếp theo ngày 08/11: [hoàn thiện verifier/evidence và kết quả run cuối](hd360_followup_verification_20261108.md). Số liệu các phần trên là lịch sử của lượt trước.
