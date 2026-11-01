# compliance

Bước 5: nhận C05, C06 và knowledge được khóa phiên bản; tạo C07 rồi tổng hợp C08.

`criterion_reasoner.reason(request, knowledge)` xử lý bốn findings C07:
`SATISFIED`, `VIOLATED`, `MISSING`, `UNKNOWN`. Criterion được hỗ trợ là
`CONTRACT_CONTENT`, `NOI_DUNG_BAT_BUOC`, `PERFORMANCE_WITH_DOCUMENTS`,
`PERFORMANCE_OR_CONDITIONAL`, `DOI_CHIEU_CO_DIEU_KIEN`, `PROHIBITED_CLAUSE`
và `CONTRACT_CLAUSE_AND_PERFORMANCE`, theo proof policy riêng của từng loại.
Hàm thuần: không đọc DB, HTTP/LLM hoặc ghi dữ liệu. Mỗi criterion trong checklist
đã xác định version đều có kết quả, kể cả khi chưa có Observation.
Kết quả giữ `PENDING`, snapshot rule thực sự được thử, criterion, metadata và stable ID.
Nếu C05 chưa resolve version, kể cả còn candidate version ID, reasoner không tự tạo
criterion hoặc finding giả; C08 vẫn giữ requirement đó với INSUFFICIENT và diagnostics.

Reasoner không diễn giải tự động câu `predicate` hoặc tìm từ khóa để đoán kết luận.
Adapter sở hữu đánh giá ngữ nghĩa, xác minh nguồn và ngoại lệ; các cờ xác minh phải
dựa trên kiểm tra thật. Engine chỉ có thể bác bỏ cờ sai qua kiểm tra cấu trúc,
không tự bật cờ hoặc duyệt knowledge. `source_available` trong rule là có căn cứ
đúng quan hệ; `source_verified` vẫn cần attestation từ adapter backend.

`grounding_validator.validate_criteria(request, knowledge, complete=False)` tái sử dụng
`shared.validation`, kiểm tra nguyên văn/offset Unicode và ownership. Hàm trả dictionary
issues theo criterion; `complete=True` thêm lý do thiếu Observation. ID/run/hash,
ownership hoặc quote sai phát sinh `ValueError`. Không có C06 selected FINAL trả
issue dẫn đến `UNKNOWN`; gắn evidence bằng C06 chỉ thuộc criterion khác là lỗi ownership.

Rule được lấy đúng criterion + finding đề xuất, không lọc bằng nhãn release của context.
JSON text/object được đọc an toàn; duplicate keys, NaN/Infinity, rule trùng/thiếu/disabled,
gate hoặc điều kiện chưa hiểu đều không tạo finding chắc chắn.

### Điều kiện chấp nhận

| Finding | Điều kiện ngoài rule ngữ nghĩa đã được review |
| --- | --- |
| SATISFIED / VIOLATED | Evidence có provenance, gates đáng tin cậy; nếu có numeric thì phép tính phải đồng ý với đề xuất. Không tự đổi sang finding đối lập khi phép tính không đồng ý. |
| MISSING | Bắt buộc trong hợp đồng và trong case hiện tại; missing policy cho phép; coverage/absence được xác minh; đủ trang, đủ phụ lục; các reliability gates đạt. Không cần quote cho nội dung không tồn tại. |
| UNKNOWN | Thiếu xác minh/facts/rule/evidence, bất đồng numeric, template cần thiết chưa điền hoặc dạng rule chưa hỗ trợ. Có `uncertainty_reason` cụ thể. |

MISSING chỉ hỗ trợ hai policy `MISSING_CHI_KHI_NOI_DUNG_BAT_BUOC_VA_DA_KIEM_TRA_TOAN_BO`
và `MISSING_ONLY_AFTER_FULL_DOCUMENT_AND_ANNEX_REVIEW`. Rule MISSING vẫn phải enabled.
Không suy ra absence từ top-K rỗng. Engine kiểm tra attestation của backend về bộ tài liệu;
DTO chunks không chứa manifest tổng số trang/phụ lục để tự chứng minh completeness.

C05 chưa xác nhận không bị Observation ghi đè. `NOT_APPLICABLE` chỉ được ghi
`UNKNOWN/excluded=True` khi C05 có `NO_MATCH`, version resolved và lý do.
Local `NO_MATCH` cần C05 confirmed, gates/provenance đủ và exclusion_reason.
Các trường hợp chưa xác định scope không được loại khỏi checklist.

### Ranh giới provider và backend

`reviewed_observations.build_verified_observation(proposal, review, request, knowledge)`
là adapter thuần cho proposal chưa đáng tin. `BackendReview` đến từ ứng dụng/reviewer,
gắn case/contract/requirement/criterion/run/snapshot và SHA256 của chính proposal.
Adapter bỏ gates, facts_verified, scope, absence và các cờ của provider; chỉ lấy xác minh
từ review độc lập. Không có review hoặc predicate chưa review thì giữ UNKNOWN.
`proposal_digest()` giúp gắn review với đúng nội dung; digest không chứng minh nội dung đúng.

`reason()` vẫn nhận Observation từ adapter backend theo contract hiện tại, để tương thích
manual demo. **Không đưa trực tiếp JSON của LLM vào reason hoặc dùng nó tạo BackendReview.**
Các DTO nội bộ không xác thực danh tính người gọi. Xác minh pháp lý, completeness và
kiểm tra thực tế thuộc adapter/reviewer. Client OpenAI đã được triển khai, còn xác thực
reviewer và luồng phê duyệt tự động nằm ngoài module này.

### Provider, chạy offline và review

`LLMObservationProvider` trong `llm_observations.py` triển khai interface `observe()`;
`analyze()` trả cả Observations và các `CriterionAnalysis` để đối chiếu. Mỗi criterion
đã có version trong checklist có một record; thiếu C06/client hoặc chạm giới hạn gọi
thì có UNKNOWN với mã lý do, không tự tạo C06 hay giả câu trả lời AI.

Luồng: C05/C06/chunks/pinned knowledge → SemanticProposal → kiểm tra quote/ID →
BackendReview độc lập → Observation → reason() → C07. Schema AI không có gates.
`checked_conditions`/`missing_conditions` nói về nội dung predicate;
`verification_requirements` ghi các kiểm tra backend còn cần thực hiện. `candidate_facts`
chỉ được lưu làm đề xuất, không tự chuyển thành facts_verified.

Trước phân tích, `CriterionVerification` có thể cung cấp facts/coverage đã được backend
kiểm chứng, gắn case/run/snapshot/criterion và verification_reference. Nó không có
predicate_verified hoặc proposal digest, nên không phê duyệt một đề xuất tương lai.
Sau phân tích, `BackendReview` gắn với digest của chính Observation proposal đó.
Hai loại record này phải đến từ backend/reviewer đáng tin, không tạo từ JSON của LLM.
Thông tin nguồn trong profile C02/C05 vẫn là bối cảnh khi chưa được xác minh.

Chứng từ ngoài có thể cung cấp `VerifiedExternalExcerpt` trong CriterionVerification:
ID và hash phải trùng đăng ký đã verified, kèm text và source_locator do backend kiểm tra.
Metadata URI/hash đơn thuần không đủ để AI đọc nội dung chứng từ. Đường này không cần C06
giả. MISSING có thể dùng attestation absence/coverage đầy đủ và không cần quote giả.

Chạy trên DB local, **mặc định offline, không gọi OpenAI và không phát sinh phí API**:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m legal_checker.modules.compliance.run_c07 `
  --case CA360_001 `
  --reference-run CA360_001_PDF360_LS2_REFERENCE
```

Runner chỉ đọc DB, nạp snapshot đã pin, tạo DEV run mới và sao chép toàn bộ C06 selected
FINAL sang run đó với lineage. Không đổi lựa chọn C06 hoặc sửa reference/seed. Output gồm
source_input.json, input.json, profile.json, verifications.json, analyses.json, c07.json,
metadata.json, report.md và review_bindings.json. Nhật ký llm_audit.jsonl chỉ có event
cho attempt API; offline/replay giữ file rỗng. Mỗi lần chạy dùng output directory mới.

Để áp dụng review cho proposal đã lưu mà không gọi API lại:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m legal_checker.modules.compliance.run_c07 `
  --input OLD/input.json --profile OLD/profile.json `
  --verifications OLD/verifications.json --replay-analyses OLD/analyses.json `
  --reviews reviewed_records.json --output-dir NEW
```

`review_bindings.json` chỉ giúp gắn identity/digest, không xác nhận gates. Giữ nguyên
input/profile/verifications khi replay; thay đổi ngữ cảnh/snapshot/prompt bị từ chối.
BackendReview là post-proposal; CriterionVerification là pre-analysis. Muốn thay các
facts dùng để phân tích phải phân tích lại, không lặng lẽ gắn chúng vào một proposal cũ.

### OpenAI tùy chọn (chưa chạy live trong đợt hoàn thiện offline)

Client dùng [Responses Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses),
strict JSON schema và store=false. Có timeout/retry hữu hạn, tôn trọng Retry-After,
không retry quota/billing hoặc lỗi refusal/incomplete/schema. Audit ghi model thực tế,
usage được API báo và hash; không lưu API key, prompt hoặc response body vào audit.
OpenAI tính phí token theo [bảng giá](https://developers.openai.com/api/docs/pricing);
không mặc định chọn model hoặc bảo đảm một model miễn phí cho tài khoản.

Khi chủ động muốn chạy có API sau này: cài `backend[ai]` theo constraints, cấu hình
OPENAI_API_KEY và OPENAI_MODEL trong .env. Chỉ cờ `--live` mới bật gọi API, kể cả khi
đã có API key. Ví dụ với input đã có C06 của criterion cần thử:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pip install -e './backend[ai]' -c constraints.txt
.\.venv\Scripts\python.exe -X utf8 -m legal_checker.modules.compliance.run_c07 `
  --case CA360_001 --reference-run CA360_001_PDF360_LS2_REFERENCE `
  --live --criterion TC_PV_HYC049_01 --max-calls 1
```

`--max-calls` giới hạn số criterion được gọi, mỗi criterion còn chịu max attempts và
total timeout của client. Criterion ngoài giới hạn vẫn có Observation UNKNOWN.
Không tự gửi cả hợp đồng: chỉ các chunks được C06 chọn cho criterion hiện tại cùng
criterion/rules/căn cứ và bối cảnh cần thiết. Không tự tìm evidence thay module retrieval.

Chứng từ ngoài dùng `ReasoningPayload.external_evidence_registry` (mặc định `[]`).
`ExternalEvidenceRegistration` gắn context, contract, requirement, criterion, ID, URI,
SHA256, trạng thái verified và reference của lần xác minh. Backend loader phải kiểm tra
nguồn/bytes/hash trước khi ghi attestation. Engine so đối chiếu đăng ký độc lập và evidence;
thiếu đăng ký hoặc chưa verified trả UNKNOWN, nhầm case/run/source/hash phát sinh lỗi.
Không dùng C06/chunk giả cho chứng từ. PERFORMANCE_WITH_DOCUMENTS cần chứng từ này;
câu hứa trong hợp đồng không chứng minh đã thực hiện.

### Numeric đã hỗ trợ

`numeric_rules.py` nhận diện **12 dạng** theo exact schema allowlist được mô tả bên dưới
và kiểm tra trong các unit tests numeric.
Ngưỡng luôn lấy từ rule đã pin; không hard-code kết luận theo criterion/case ID.

| Khóa numeric rule | Facts bắt buộc (ngoài units/scope) |
| --- | --- |
| first_payment_including_deposit_lte_ratio | contract_price, first_payment_excluding_deposit, deposit |
| prehandover_cumulative_lte_ratio + foreign_seller_art10_4_lte_ratio | contract_price, cumulative_payment, before_handover=True, foreign_seller_art10_4 là bool |
| before_certificate_cumulative_lte_ratio | contract_price, cumulative_payment, before_certificate=True |
| maintenance_ratio + separate_from_sale_price | maintenance_amount, maintenance_base, maintenance_base_kind=APARTMENT_OR_SOLD_AREA_VALUE, separate_from_sale_price là bool |
| warranty_min_months | warranty_months, warranty_unit=MONTH, warranty_start=COMPLETION_AND_ACCEPTANCE_INTO_USE |
| application_submission_max_days | submission_elapsed_days, submission_unit=DAY, submission_start=HANDOVER, submission_event=APPLICATION_SUBMISSION, application_submitted=True, buyer_voluntarily_self_files=False |

Các amount/base cần `<tên_fact>_unit` cùng VND/USD/EUR; không tự đổi tiền tệ.
`numeric_scope` phải trùng scope trong rule: FUTURE_COMMERCIAL, NEW_PROJECT hoặc
DEVELOPER_SALE_MULTIPLE_OWNERS_NEW_RULES tương ứng schema. Facts phải được backend xác minh.
Tính Decimal và so tích chéo; từ chối NULL, bool làm số, NaN/Infinity, mẫu số <=0,
giá trị âm và precision/magnitude ngoài giới hạn 80 digits/exponent. Không dùng float arithmetic.

Sáu biến thể bổ sung trong inventory:

- Deposit: deposit/sale_price, các `_unit` và eligible_before_collection là bool.
- First-payment 2014: amount/unit như bảng, thêm deposit_inclusion_reviewed=True,
  deposit_inclusion_review_reference và deposit_included_in_first_payment là bool.
- Prehandover 2014: dùng đúng fact đã pin `ho_so_hop_dong.ben_ban_co_von_nuoc_ngoai`.
- Before-certificate 2014: numeric_scope=FUTURE_FORMED_KDBDS_2014.
- Maintenance 2014: maintenance_amount/apartment_value và `_unit`,
  denominator_definition_reviewed=True, denominator_definition_review_reference,
  included_in_sale_payment là bool.
- Warranty 2014: numeric_scope=APARTMENT_NEW_BUILD_NHAO_2014, cùng facts thời hạn/mốc.

Rule cấp nhóm dùng chung nhiều criterion cần binding từ backend về `numeric_target`,
`numeric_target_reviewed=True`, `numeric_target_review_reference`. Deposit cho phép
DEPOSIT_CAP, DEPOSIT_ELIGIBILITY, DEPOSIT_PRICE hoặc ALL_CONSTRAINTS; DEPOSIT_PRICE cần
sale_price_stated_in_agreement. Maintenance 2014 cho phép MAINTENANCE_RATIO,
MAINTENANCE_PAYMENT_INCLUSION hoặc ALL_CONSTRAINTS. Không suy ra target từ ID/keyword.
Thiếu review định nghĩa mẫu số, cách tính deposit hoặc target thì UNKNOWN; nhận diện
schema không đồng nghĩa đã xác minh ý nghĩa pháp lý cho case thực tế.
Deadline hiện chỉ so khoảng ngày của lần nộp hồ sơ đã có chứng từ; chưa tự tính lịch/ngày
nghỉ hoặc suy ra vi phạm từ việc chưa nộp. Nhánh người mua tự làm cần review applicability.

Các loại criterion có điều kiện cần facts đã được backend xác minh:
evaluation_target=CONTRACT_CONTENT/PERFORMANCE và condition_triggered khi có điều kiện
phát sinh. Nhánh PERFORMANCE cần chứng từ ngoài; lời hứa không tạo SATISFIED về thực hiện.
PROHIBITED_CLAUSE đề xuất SATISFIED về vắng điều cấm cần coverage/absence/trang/phụ lục
đầy đủ và evidence quy chiếu được. Optional choice cần optional_choice_confirmed là bool
đã review; không được đổi unknown thành NOT_APPLICABLE. Rule hybrid phải nêu rõ target.
`case_facts_required=True` đòi facts có nội dung và facts_verified; exception_ids phải thuộc
đúng criterion/version. Dạng policy/schema khác vẫn UNKNOWN rõ lý do.

Aggregation C08, compliance service và workflow bước 5–7 đã được triển khai.
Demo `manual_observations.py` không đổi flags, vẫn UNKNOWN do local applicability,
source_verified và exceptions_resolved chưa xác minh, cùng facts còn thiếu theo policy.

Chạy unit tests không cần PostgreSQL:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q -c backend/pyproject.toml backend/tests/unit/test_criterion_reasoner.py backend/tests/unit/test_c07_findings.py backend/tests/unit/test_numeric_rules.py backend/tests/unit/test_grounding_validator.py backend/tests/unit/test_reviewed_observations.py backend/tests/unit/test_manual_observations.py backend/tests/contract/test_architecture.py
```

Queries/mappers nằm trong repository của module; engines nhận DTO/KnowledgeSnapshot,
không mở kết nối DB hoặc gọi HTTP/LLM bên trong reasoner/aggregator.

Input provider dùng chung một interface: `ObservationProvider.observe` trong `observations.py`,
được inject qua `DraftModules.observations`. Adapter tạo các `Observation` từ C05/C06,
profile/facts và knowledge; các gates phải dựa trên kiểm tra thật, không tin flags do
LLM tự khai báo. Observation vẫn là đầu vào đề xuất, chưa phải C07 đã xác minh.

## C08 và service compliance-only

`requirement_aggregator.aggregate(context, knowledge, criteria, requirements)` nhóm
theo `yeu_cau_ca_id` và đối chiếu toàn bộ checklist của requirement version. C07 cần
snapshot context, contract và knowledge hash; thiếu/lệch pins hoặc trộn contracts bị
từ chối. Policy `AGG_CAN_HO_V1` đã pin được áp dụng theo thứ tự:

1. Chưa confirmed, thiếu policy hoặc thiếu C07 findings → INSUFFICIENT.
2. Có VIOLATED → NON_COMPLIANT.
3. Còn UNKNOWN → INSUFFICIENT.
4. Tất cả MISSING → NON_COMPLIANT.
5. Có SATISFIED cùng MISSING → PARTIAL.
6. Tất cả SATISFIED → COMPLIANT.

Không dùng tỷ lệ SATISFIED để thay policy. N/A chỉ được loại với lý do và đủ điều
kiện; không che knowledge/fact gap. C08 giữ counts, coverage, expected/missing criterion
IDs, rule version và snapshots. Policy lạ/mâu thuẫn giữ diagnostics.

`service.evaluate_compliance(ReasoningRequest, knowledge)` tạo C07/C08 và C10/C11 chỉ
cho nguồn compliance. `workflows.steps_5_7.evaluate(PipelineRequest, knowledge)` nhận
thêm C09, tạo full pipeline và giữ trạng thái citation NOT_RUN/COMPLETED. C09 thiếu
provenance không được nâng thành risk khẳng định. Các hàm đều nhận dependency được
inject; `DraftAssessmentWorkflow` nối chúng với upstream implementations mà caller
cung cấp. Không có OCR/Scope/Temporal/Retrieval/Citation hoặc BackendReview giả.

## Runner nhóm C bước 5–7

`legal_checker.modules.assessments.run_group_c` không tạo paid client. Offline đọc
upstream C02/C05/C06 local, giữ flags chưa xác minh và tạo run mới; replay dùng analyses
đã xuất cùng input/profile gốc. Cờ không hợp lệ bị từ chối, thư mục output phải mới.
Export dùng staging rồi publish và JSON keys xác định; `input.json`/`output.json`,
C07/C08/C10/C11, diagnostics, hashes/counts và sidecars phản ánh kết quả engines thật.

Chạy từ root repo. DB phải có upstream rows và knowledge snapshot đúng case pin;
runner không tự thay pin/review của case. Với run demo đã chuẩn bị và cách khởi động
PostgreSQL test, xem [bàn giao nhóm C](../../../../../docs/group_c_handoff.md).

```powershell
# DATABASE_URL trỏ DB local đã chuẩn bị; không đưa mật khẩu thật vào repo.
$tag = [guid]::NewGuid().ToString('N')
$offline = "outputs/group_c_offline_$tag"
.\.venv\Scripts\python.exe -X utf8 -m legal_checker.modules.assessments.run_group_c --case CA360_001 --reference-run CA360_001_PDF360_LS2_REFERENCE --output-dir $offline

# Save cùng input/case/run trong một transaction; không lấy output làm đáp án.
$saved = "outputs/group_c_saved_$tag"
.\.venv\Scripts\python.exe -X utf8 -m legal_checker.modules.assessments.run_group_c --input "$offline/input.json" --save --output-dir $saved

# Đọc chính xác run đã lưu, không khởi tạo Knowledge/provider hoặc chạy engines.
$meta = Get-Content -LiteralPath "$saved/metadata.json" -Raw | ConvertFrom-Json
.\.venv\Scripts\python.exe -X utf8 -m legal_checker.modules.assessments.run_group_c --case $meta.case_id --read-run $meta.run_id --output-dir "outputs/group_c_read_$tag"

# Replay giữ nguyên proposal/context bindings và profile; không gọi model.
.\.venv\Scripts\python.exe -X utf8 -m legal_checker.modules.assessments.run_group_c --input "$offline/input.json" --replay-analyses "$offline/analyses.json" --profile "$offline/profile.json" --output-dir "outputs/group_c_replay_$tag"
```

`--citations` chỉ nhận C09 của đúng case/run; nếu không chạy upstream thì giữ NOT_RUN.
`--citations-completed` biểu diễn nhánh đã chạy nhưng không có finding. Review,
verifications và external registry phải là sidecars backend đáng tin, gắn đúng run,
snapshot và proposal digest; thiếu chúng giữ UNKNOWN, không tự bật gates.

`--save` dùng Store ghi normalized rows, full DTO, input/output snapshots, pins và
`assessment_output_lineage` trong transaction. Retry cùng input/case/run trả output
đã lưu; input khác cùng run conflict. `--read-run` chỉ chấp nhận `--case`/`--output-dir`,
kiểm tra checksum, pins, knowledge, normalized rows và lineage, không recompute.
Nhóm D dùng `Store.get/get_input/get_lineage` cho exact run, không chọn “run mới nhất”
hoặc chạy C07/C10/C11 khi dựng report. Dữ liệu legacy thiếu lineage/provenance giữ lỗi
tường minh; không fallback sang QA EXPECTED.

Mốc kiểm chứng giai đoạn 2: 1009 tests trong phạm vi lõi/workflow/runner/DB liên quan
đã chạy đạt, không skip, với PostgreSQL 18.4 local. Đây là kết quả có phạm vi; kết quả
checks toàn repo và artifacts bàn giao cuối được ghi riêng trong báo cáo nhóm C.
