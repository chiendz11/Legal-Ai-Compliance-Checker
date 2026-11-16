# Recipe C07 verification cho người 4 và composition của người 5

Đọc [playbook chung](../guides/parallel_development_playbook.md) và
[numeric dictionary](../contracts/data_dictionary.json). Đây là hợp đồng triển khai,
không phải thông báo verifier nghiệp vụ đã hoàn thành. Model thực thi là
`modules/compliance/verification.py:CriterionVerification`; schema tương ứng là
[criterion_verification.schema.json](../contracts/criterion_verification.schema.json).

## 1. Vai trò của ba loại dữ liệu

| Đối tượng | Tạo bởi | Xác nhận điều gì? |
|---|---|---|
| CriterionVerification | Backend/reviewer độc lập với proposal | Facts, local applicability, coverage/nguồn đã kiểm tra cho criterion/run cụ thể |
| SemanticProposal/Observation proposal | LLM/rule adapter | Đề xuất nội dung và quote; không được tự bật gates |
| BackendReview | Backend sau khi thấy proposal và checks | Có chấp nhận predicate/proposal cụ thể thành draft không; bind proposal digest |

CriterionVerification không có quyền tự phê duyệt proposal chưa tồn tại. BackendReview
khác C12 human report review. Quote đúng chưa chứng minh numeric/exception/performance.

## 2. Chuẩn bị input trước khi gọi model

1. Xác nhận context.case/run/hash và contract, C05 requirement instance/version.
2. Lấy criteria theo version; unresolved version không tạo criterion giả. C05 candidate
   không được promoted chỉ vì knowledge.criteria_for có kết quả.
3. Workflow chạy Retrieval trước. LLMObservationProvider nhận selected FINAL C06 và
   kiểm ownership/grounding. Hàm verify hiện không nhận C06: verifier đọc profile.facts/
   evidence và full active chunks để kiểm facts/coverage độc lập, không query C06 seed
   thay cho C06 của run. Không tự thêm tham số retrieval vào interface.
4. Đọc criterion.dieu_kien, decision rules enabled, exception IDs và legal basis trong
   snapshot. Rule chưa hỗ trợ hoặc nguồn mâu thuẫn phải giữ issue, không chọn rule đầu.
5. Lấy facts gốc + chứng từ ngoài; map canonical names/units theo nhánh hiện tại. Facts
   mâu thuẫn hoặc không có nguồn không được thông qua facts_verified.
6. Tạo CriterionVerification có reference ổn định về các checks thật. Chỉ điền những
   gì đã kiểm; không tạo một record bật tất cả cờ để tránh UNKNOWN.
7. Gọi LLM proposal; kiểm schema/IDs/quote/offset, rồi BackendReview cho đúng proposal.
8. reason() kiểm lại gate/predicate/numeric để tạo C07; aggregator tạo C08. Lưu actual
   dispositions/diagnostics, không sao chép expected hoặc flags từ provider.

## 3. Coverage cùng extraction

verify nhận keyword `coverage: DocumentReadCoverage | None`. DTO có contract ID,
source SHA, extraction_version, page_count và unreadable_pages từ parser của chính
run. Source thật truyền metadata; reference DI không có metadata thật thì None.
Schema nằm ở [document_read_coverage.schema.json](../contracts/document_read_coverage.schema.json).

all_pages_have_text chỉ nói mỗi trang có text, chưa chứng minh text không thiếu,
reading order đúng, đã nhận đủ phụ lục hoặc đã rà đầy đủ clause. Provider vẫn phải
kiểm chất lượng/coverage theo proof obligation trước khi đặt all_pages_readable,
coverage_complete, all_related_documents_received hoặc absence_verified. Nếu không
có evidence cho các attestations này, giữ False; không suy từ len(chunks).

## 4. Bảng proof obligations theo loại criterion hiện được engine hỗ trợ

| loai_kiem_tra | Input và checks cần có | Cách xử lý thiếu |
|---|---|---|
| CONTRACT_CONTENT / NOI_DUNG_BAT_BUOC | Attributable contract quote + reviewed predicate/rule/basis; local applicability và facts nếu rule yêu cầu | UNKNOWN nếu chỉ thiếu selected text/check; MISSING chỉ khi toàn bộ absence policy thỏa |
| PROHIBITED_CLAUSE | VIOLATED cần clause thật; SATISFIED cần coverage_complete/absence_verified, đọc đủ pages/related documents | Không tìm top-K không chứng minh không có clause cấm |
| PERFORMANCE_WITH_DOCUMENTS | Registered external evidence đúng hash/ownership, contents/excerpts được backend kiểm tra, predicate đúng | Contract promise không đủ; thiếu chứng từ → UNKNOWN |
| PERFORMANCE_OR_CONDITIONAL | evaluation_target được verify; condition_triggered=true; PERFORMANCE cần external proof | CONTRACT_CONTENT không đủ để SATISFIED performance |
| DOI_CHIEU_CO_DIEU_KIEN | evaluation_target, condition_triggered, scope/ngoại lệ của current criterion; proof phù hợp target | Không default condition_triggered từ sự có mặt của một đoạn |
| CONTRACT_CLAUSE_AND_PERFORMANCE | Chọn rõ target; CONTRACT_CONTENT cần clause; PERFORMANCE cần external proof; không kết luận thay nhánh chưa có proof | Giữ phạm vi CURRENT_CRITERION và nêu target thực đã kiểm |

Nếu rule có conclusion_scope_required hoặc performance_requires_receipt_evidence,
áp dụng thêm guard của rule. Không đổi loai_kiem_tra để làm một ca dễ đạt kết luận.

## 5. Control facts và local applicability

Các tên dưới đây đã được criterion_reasoner sử dụng; dictionary phải giữ đồng bộ:

- `evaluation_target`: CONTRACT_CONTENT hoặc PERFORMANCE, gắn current criterion.
- `condition_triggered`: bool verified; chỉ True khi có evidence condition đã xảy ra.
- `optional_choice_confirmed`: bool verified theo policy lựa chọn. False không tự là
  vi phạm; chỉ excluded khi criterion policy cho phép và đầy đủ điều kiện.

Ba tên là backend verification controls, không yêu cầu người dùng điền literal flags
vào PDF. Không dùng field khác tên hoặc số 0/1 thay strict bool. Nếu có case_facts_required
mà catalog chưa xác định đủ ý nghĩa facts, owner 4 phải bind theo predicate có nguồn;
không dùng một fact không liên quan để vượt điều kiện “facts không rỗng”.

Local applicability NO_MATCH cần exclusion policy/reason được hỗ trợ, không dùng để
che processing error hoặc legal basis thiếu. UNKNOWN không đồng nghĩa không áp dụng.

## 6. Numeric và nhánh dùng chung

Danh mục canonical numeric fields nằm trong dictionary; threshold luôn từ rule pin.

| numeric_kind | Điều cần phân biệt khi bind facts |
|---|---|
| deposit_lte_ratio | sale_price, deposit, đơn vị; eligibility khác cap/price declaration; numeric_target được review |
| first_payment_including_deposit_lte_ratio | first_payment_excluding_deposit + deposit, cùng currency/contract_price và numeric_scope |
| first_payment_lte_ratio | Cách tính đã gồm đặt cọc phải có deposit_inclusion_reviewed/reference riêng |
| prehandover_cumulative_lte_ratio | before_handover và đúng nhánh seller/current/legacy; foreign flag chưa rõ không chọn ngưỡng tùy ý |
| before_certificate_cumulative_lte_ratio | before_certificate là điều kiện đã kiểm, không suy từ việc PDF không nhắc giấy chứng nhận |
| maintenance_ratio | Current maintenance_base khác legacy apartment_value; separate/included và denominator review/target có nghĩa riêng |
| warranty_min_months | MONTH + warranty_start đúng policy, không tự lấy ngày bàn giao dự kiến làm commencement |
| application_submission_max_days | APPLICATION_SUBMISSION khác cấp giấy; actual handover/submission và nhánh buyer self-files có proof |

Nhóm fields dictionary là superset có điều kiện, không phải bắt mọi criterion có toàn
bộ facts của nhóm. Rule shape lạ/mẫu số 0/unit lệch/null/bool thay số → UNKNOWN/issue,
không ép giá trị. Dùng threshold mới phải kiểm below/equal/above bằng rule pin mới.

## 7. MISSING và absence

Chỉ CONTENT_TYPES được hỗ trợ MISSING khi criterion bắt buộc có nội dung trong hợp
đồng, missing_policy được hỗ trợ, mandatory_confirmed, coverage_complete,
absence_verified, all_pages_readable, all_related_documents_received và reliability
gates đều đạt. Phải xác định bộ tài liệu đã rà gồm thân/phụ lục nào.

Không đủ hồ sơ để chứng minh performance khác với chứng minh nội dung bắt buộc
vắng trong bộ hợp đồng. Không fabricate quote cho nội dung không tồn tại.

## 8. Registry và dependency injection

EvidenceRegistryProvider.load(context, case, knowledge) tạo registrations cho đúng run.
Provider kiểm source bytes/hash trước verified=True. CriterionVerification.external_excerpts
phải tham chiếu registration verified cùng SHA và criterion. Metadata URL không là
chứng minh contents. Source bí mật/PII không được in raw vào audit kỹ thuật.

Người 5 gọi build_services(settings, verification_provider=actual_verifier,
external_registry_provider=actual_registry). Có port nhưng không inject implementation
thì task chưa đủ DoD. Chưa có provider không được dùng fake reviewer ở đường khách hàng.

Hai providers là hai dependency riêng, không tự nhận output của nhau. Signature verify
chỉ có context, profile, requirements, chunks, knowledge và coverage; không có case,
retrieval hoặc registry argument. Người 4 có thể dùng cùng read-only evidence repository
qua constructor cho cả hai implementations; người 5 inject chúng vào API và worker.
Repository chọn exact case/run/hash, registrations/excerpts dùng cùng evidence ID/SHA.
Không đọc registry reference của run khác, hoặc kỳ vọng workflow tự truyền một field
chưa tồn tại. Nếu cần thay signature, sửa Protocol/composition/schema/tests cùng PR.

## 9. Bằng chứng bàn giao cho từng criterion đã mở hỗ trợ

Cần có C05 resolved/confirmed phù hợp, C06/source package, facts/units, verification
reference, proposal/check results, C07/C08 và expected được review độc lập. Kèm một
ca đủ căn cứ và ca thiếu/khác branch để chứng minh không “approve all”.

Tests hiện có: automatic_draft_review, numeric_rules, c07_extended_types,
reviewed_observations, llm_observations và group_c_core. Các tests giả lập checks
chứng minh engines/guards; verifier thật còn phải kiểm tra source/facts trên ca DEV/VAL.


## 10. Implementation source-only và kịch bản đồ án

Composition hiện đã inject SourceFactVerifier; source/quote/facts checks không thay
criterion-specific legal verification. SyntheticScenarioEvidence là lựa chọn rõ qua
SYNTHETIC_SCENARIO_PATH, chỉ khớp PDF/knowledge hash đã khai báo. Không dùng chế độ
này để coi chứng từ giả lập là hồ sơ khách hàng thật. [Chi tiết và cấu hình](../guides/synthetic_evidence_and_inference_fixes_20261107.md).

## 11. Luồng rà toàn văn và nguồn bất biến — 08/11/2026

- Người 2: trích ba facts `maintenance_account_number`, `maintenance_account_holder`,
  `maintenance_bank` khi văn bản ghi rõ; giữ quote/offset và xung đột. Không suy ra
  số tài khoản bảo trì từ tài khoản thu tiền mua nhà.
  `rules-v10` hỗ trợ các nhãn này trên ba dòng riêng; quote phải mang nhãn chứng minh
  vai trò. Người 4 có `C07_EXACT_CONTENT_V3` cho phần ghi thông tin của
  `TC_ACCOUNT_2015_03`; xác nhận tài khoản/ngân hàng thật vẫn là nghĩa vụ khác.
- Người 3: truy xuất theo criterion, bổ sung topic anchors có tên rõ (thời gian thanh
  toán, hợp đồng trả dần bằng văn bản, hồ sơ bàn giao). Candidates từ full review phải
  quay lại C06 cùng requirement/criterion/run, không chỉ nằm trong prompt C07.
- Người 4: FullDocumentReviewer rà tất cả active chunks theo batch chồng lấn một
  chunk. PROHIBITED_CLAUSE dùng semantics hành vi bị cấm, không chỉ keyword.
  CONTENT chỉ bật qua `full_document_review_required`. Bỏ sót chunk/criterion,
  nguồn lạ, hết call budget hoặc UNCERTAIN không được chứng minh vắng nội dung.
  `PRESENT` chỉ tìm candidates: chuyển vào C06 để semantic C07 đối chiếu lại, không
  tự đổi thành VIOLATED/SATISFIED. Kết luận có nội dung phải mang quote hoặc nguồn
  đăng ký; batch thiếu nguồn được repair riêng một lần, vẫn thiếu thì UNKNOWN.
- Người 5: gọi refiner trước C07; trả C06 mới, validate rồi mới reasoning. Lưu
  coverage proof bất biến và hiển thị NOT_TRIGGERED riêng. Giữ human review PENDING.
- Người 1: giữ scenario/knowledge/PDF hash tương thích. Synthetic chỉ nhận đúng
  source/snapshot, lưu cả revision cũ vào evidence cache, không sửa workbook/DB
  seed hoặc lịch sử report khi chỉ nâng implementation.

Revision mới, sáu predicate nội dung có nguồn và hướng dẫn áp dụng catalog ở DB
local: [complete_runtime_alignment_20261108.md](../guides/complete_runtime_alignment_20261108.md).

`ASSESSMENT_FULL_DOCUMENT_REVIEW=on` bật lượt rà khi có LLM và source cache; tổng
ngân sách của rà toàn văn và reasoning dùng chung `ASSESSMENT_LLM_MAX_CALLS`. Một
criterion trong một batch rà (kể cả repair) tốn một đơn vị, cùng đơn vị criterion
analysis của reasoner; số HTTP requests có thể nhỏ hơn nhờ batching. Tắt cấu
hình không làm absence trở thành đúng; các criterion thiếu proof vẫn UNKNOWN.

Chữ ký/con dấu cần kiểm ảnh. Chứng từ SOURCE_PINNED_VISUAL_INSPECTION hiện chỉ cho
đúng PDF HD360_001 synthetic và các trang đã nhìn trực tiếp; xác nhận **thiếu** chữ
ký/nội dung ký không tạo chữ ký/con dấu hoặc chứng nhận người thật đã duyệt.
