# Sổ tay triển khai song song cho năm người

> Dataset cho DB phát triển mới: [PDF360 v4 r2 — 10/11](dataset_pdf360_v4r2_runtime_20261110.md).
> Dùng PDF cùng hash, snapshot đã duyệt; các hướng dẫn migration của release cũ chỉ áp dụng cho release tương ứng.


Cập nhật luồng dự thảo 09/11: [quy ước và trách nhiệm năm người](baseline_v3_draft_review_fix_20261109.md).
Nâng Alembic trước khi chạy API mới; không seed lại workbook chỉ để nhận hai cột vận hành.

Baseline dữ liệu hiện hành: [PDF360 v4 r2 — 10/11](dataset_pdf360_v4r2_runtime_20261110.md). Bản 07/11 và các blockers 06/11 bên dưới là lịch sử; snapshot mới đã có phê duyệt của chủ dự án.

Baseline tài liệu: **PDF360_V4R2_20261110**, tiếp tục INTEGRATION_V1. Đây là hướng
dẫn thực hiện đã chốt, không phải báo cáo mọi module đã nghiệm thu. Models/JSON Schema
vẫn dùng contract_version `1.0`; tên baseline tài liệu không phải enum mới cho DTO.

Đọc theo thứ tự: [đặc tả tích hợp](../contracts/integration_spec.md) →
[dictionary](../contracts/data_dictionary.md) → phần người mình bên dưới →
[recipe verifier](../modules/criterion_verification_guide.md) khi làm C07 →
[ma trận nghiệm thu](../contracts/handoff_acceptance.json).

## 1. Những quyết định không để mỗi người tự chọn

| Chủ đề | Quyết định chung |
|---|---|
| Kiến trúc | Modular monolith; Python DTO nội bộ; API/worker cùng image; không tạo HTTP cho mỗi module |
| Nguồn thật | modules đọc bytes có SHA đúng; không dùng expected khi xử lý thất bại |
| Nguồn dev độc lập | C01/PDF hoặc upstream reference của module; expected của chính module chỉ dùng chấm sau chạy |
| Live scope | Toàn snapshot pin (323 families); reference mới cũng xét toàn catalog trong chế độ DRAFT_REVIEW, so đúng ASSESSMENT_SCOPE |
| Output live | workflow_runs.draft_json; report_versions; review_events; không JOIN seed thay live output |
| DB normalized | Documents lưu để consumer dùng metadata; standalone C dùng Store/lineage; các recipe SQL phải nêu rõ chế độ |
| Thiếu dữ liệu | null/UNKNOWN, có nguyên nhân; không tự đổi false/0 hoặc ngày thay thế |
| Điều khoản và thực hiện | evaluation_target phân biệt CONTRACT_CONTENT/PERFORMANCE; lời hứa không phải chứng từ thực hiện |
| Xác minh | Knowledge review, source integrity, grounding, facts/conditions và report approval là các lớp riêng |
| Chunk và quote | ID/version + text gốc; quote offset tính theo text gốc của chunk, không theo search text |
| Citation | C03 giữ vị trí; C09 không quyết định checklist; C10 hội tụ hai nhánh |
| LLM | Chỉ proposal; không nhận flags của AI như attestations; budget/error không phải pháp lý |
| Report | C13 ghép snapshot đúng run; không chạy thêm AI để tự đổi kết luận |
| Release | Đủ source/contract/implementation/qualification; không suy từ unit pass hoặc pods Ready |

Revision tri thức 06/11 chốt typed fields `la_giao_dich_dien_tu` và
`co_thoa_thuan_trong_tai`; field `can_danh_gia_trong_tai` chỉ còn ở snapshot cũ.
Mốc chọn phiên bản và sự kiện thực hiện đã có
[policy thống nhất](../contracts/knowledge_applicability_policy.md). Producer vẫn
phải implement extraction/fact mapping có nguồn; không mặc định false hoặc tự tạo
ngày. Release 10/11 dựng lại runtime/QA từ PDF v4 r2 cùng snapshot được duyệt; DB cũ không tự đổi. Dùng hướng dẫn PDF360 v4 r2 để cài vào DB mới.

## 2. Phạm vi sản phẩm và đầu vào được hỗ trợ

MVP hiện đọc PDF có text layer. PDF scan chưa OCR và DOCX chưa parser phải fail rõ;
upload lưu được file chưa đồng nghĩa inference đã hỗ trợ format đó. Người 2 bổ sung
hỗ trợ cùng tests và update capability trước khi mở nhãn supported trên UI.

Một PDF đủ để đánh giá nội dung một số điều khoản; kết luận về thực hiện nghĩa vụ
cần chứng từ/sự kiện ngoài. Nếu chỉ có hợp đồng, các criterion cần proof ngoài giữ
UNKNOWN. Chọn một bộ demo đủ dữ liệu để minh họa nhãn rõ, đồng thời giữ ca thiếu
dữ liệu và mâu thuẫn để kiểm tra hệ thống có từ chối kết luận sai hay không.

HD360_001 hiện là ca regression cho các thiếu sót đã phát hiện, không phải ca chứng
minh toàn pipeline đã có đủ facts. Không sửa expected của nó chỉ để mọi nhãn xanh.
Baseline [FULL90 theo nguồn hiện có](../contracts/source_observed_extraction_baseline.md)
chốt phần extractor có thể lấy và consumer dùng. Giữ PDF đã điền làm đầu vào cố
định; không viết thêm dữ kiện để tránh UNKNOWN ở một nhánh chưa đủ nguồn.

## 3. Ownership: một người chịu trách nhiệm chính cho mỗi điểm

| Người | Vùng code/dữ liệu chính | Bắt buộc bàn giao |
|---|---|---|
| 1 | Dataset/catalog release, configs manifest, Alembic, DB connection, storage/audit infrastructure, CI/infra/GitOps | Pin + receipt, migration/data compatibility, reproducible setup và inventory gaps |
| 2 | modules/documents và document upload API phối hợp 5 | C02/chunks/C03 thực từ bytes, metadata + writer, nguồn/coverage/capability |
| 3 | applicable_law/citation_validation/retrieval | C04/C05/C06/C09 với reason, selection, date/version và provenance |
| 4 | compliance/risks/recommendations | Verifier **có implementation**, C07/C08/C10/C11 và tests theo predicate/type/branch |
| 5 | workflows/api composition, cases/assessments/reviews/reports/accounts và frontend | Inject module thật, lifecycle, auth/tenant, report/review/export, E2E và UI semantics |

Contracts/dictionary do người 1 điều phối version; producer và consumer phải cùng
xác nhận ý nghĩa. Person 5 sở hữu composition/config runtime; người 1 sở hữu secrets/
deploy settings. Person 2 trích citation, person 3 xác thực citation, person 4 map
citation risk, person 5 render: không chuyển trách nhiệm giữa bốn việc này.

Đây là quy trình bàn giao, không thay ruleset GitHub hoặc tự tăng số approval.

## 4. Cách mỗi người phát triển độc lập

1. Lấy cùng baseline code đã được maintainer publish; giữ phần code đang làm. Nhánh
   feat/integration-contract-alignment hiện cần publish/merge trước khi cả nhóm fetch được.
2. Mỗi dev dùng PostgreSQL riêng, dataset đúng manifest pin. Không seed DB k3d của
   thành viên khác. Giữ dataset/workbook/PDF/keys/DB ngoài Git.
3. Chọn ca DEV và upstream mẫu đúng module, đúng case/run/hash. Không dùng answers TEST.
4. Repository map rows → typed input, validate trước xử lý. Không SELECT toàn bộ rồi
   nhét vào DTO hoặc default trường để qua validation.
5. Chạy implementation module, rồi consumer nhận output đó trong handoff test.
6. Expected chính module chỉ dùng đối chiếu sau chạy; provider mock có nhãn TEST,
   không tạo audit attempt thật hoặc báo là live inference.
7. Khi upstream thật sẵn sàng, thay fixture adapter bằng implementation thật mà giữ
   cùng contract; chạy pair test rồi full flow. Không đợi cuối đồ án mới ghép.

| Người đang làm | Được dùng upstream seed/reference nào? | Không được dùng làm input để tự tạo đáp án |
|---|---|---|
| 2 | C01 + bytes PDF | C02/C03 expected |
| 3 scope/temporal | C02 + knowledge, rồi C04 khi test Temporal riêng | C04/C05 expected của đúng phần đang test |
| 3 retrieval/citation | C05 + chunks/criteria hoặc C03 + profile/knowledge | C06/C09 expected |
| 4 reasoning | C05/C06/chunks/facts/đăng ký chứng từ đã được bàn giao | C07/C08 expected |
| 4 risk/rec | C07/C09 hoặc C10 khi test riêng | C10/C11 expected của phần đang test |
| 5 | Output mẫu dựng layout; ModuleSource giả cho transport tests | Không hiển thị reference thành run khách hàng đã xử lý |

## 5. Gói bàn giao cụ thể của từng người

### Người 1: data/schema/platform

- Công bố dataset/workbook/source hashes và knowledge hash; phân biệt schema_version,
  dataset_version và legal_knowledge_version. Cùng data revision không có nghĩa code
  của mọi dev hoặc extraction version phải giống nhau.
- Cung cấp DEV/VAL để dev; MASTER chỉ evaluator; TEST_INPUTS không answers. Các biến
  thể cùng nguồn gốc giữ cùng split group; không tuning trên held-out answers.
- Review catalog gaps với người 3/4 bằng nguồn luật trong knowledge; không đổi flags
  thành review complete để thay việc bổ sung marker/mapping.
- Thay schema dùng migration mới; data release dùng seed DB mới/update phù hợp.
  Rechunk toàn corpus không được coi như reviewed-flags update đơn giản.
- Bằng chứng setup/backup/restore/rollout có môi trường, code/image/GitOps/DB pins.

### Người 2: Documents

- Nhận SourceDocument đã pin, đọc bytes qua SourceStorage, kiểm SHA trước parser.
- Output đồng thời gồm profile/subjects/facts/markers, chunks và C03. Một quote giữ
  original chunk text; search normalization không sửa evidence text.
- Với trang/phụ lục không đọc được, ghi coverage thiếu. Không đánh dấu đọc đủ bằng
  việc tổng số chunks > 0. Trường không tìm thấy khác lỗi parser/format chưa hỗ trợ.
- DocumentRepository.save xong trước metadata consumers. Profile DTO của run mới là
  nguồn thật cho Scope; bảng profile đơn cũ không thay DTO extraction mới.
- Chạy lại cùng extraction version không nhân đôi; đổi algorithm/source phải version
  mới. Không đòi chunker mới tạo đúng số chunk như fixture.
- Kèm test phát hiện facts bỏ sót, quote sai, conflict trong thân/phụ lục và citation
  lặp; công bố unsupported formats thay vì trả output rỗng như thành công.

### Người 3: Scope, Temporal, Retrieval, Citation

- Scope chỉ dùng profile/subjects/context được contract hỗ trợ; mọi điều kiện có
  nguồn và three-valued logic. Thiếu field → UNKNOWN, khác NO_MATCH.
- Temporal chọn đúng mốc và interval; không lấy ngày ký bù ngày thu. UNKNOWN có
  candidate version phải giữ candidate_version_only và reason, không coi resolved.
- C06 chỉ tham chiếu chunk đang được truyền, đúng version/criterion/run. Không có
  selected evidence là miss/không tìm thấy, chưa phải MISSING hoặc VIOLATED.
- Hiện producer dùng giai_doan=FINAL; consumer chỉ dùng duoc_chon=true + FINAL để
  lập luận. Đổi pipeline stages phải cập nhật shared contract/consumers trước.
- C03 được nhóm văn bản khi vẫn giữ occurrences; không đo extraction recall bằng
  số nhóm. Name/year có thể tạo candidates, chưa đủ chính sách định danh duy nhất.
- C09 live có CitationProvenance; status tại relevant date khác current status. Domain
  UNKNOWN không thành VALID. C09 không sửa C05/C08.
- Bàn giao Recall@K/MRR và source-span relevance trên annotations độc lập; không lấy
  selected rows của chính retriever làm gold để chấm lại retriever đó.

### Người 4: Verification, Compliance, Risks, Recommendations

- Implement CriterionVerificationProvider và dùng recipe theo loại criterion ở
  tài liệu riêng. Một Protocol, DTO hoặc constructor không được đóng task verifier.
- Giữ evaluation_target, condition_triggered, optional_choice_confirmed đúng nguồn;
  chúng là control facts backend kiểm tra, không phải ba ô bắt buộc trong PDF.
- Numeric bind current criterion/branch/target; threshold từ rule pin; Decimal + unit.
  Không ánh xạ mọi giá hợp đồng vào mọi mẫu số; không chấp nhận AI tự xác minh facts.
- MISSING/absence và performance phải có proof tương ứng. Giữ UNKNOWN khi một gate
  thiếu, nhưng ghi rõ data missing / unsupported / not processed / provider failed.
- ComplianceOutput của helper compliance-only giữ nhánh compliance; full steps_5_7.evaluate/PipelineResponse hợp nhất C09→C10/C11. Report builder nhận merged risks/recommendations riêng; không nhét citation risks vào ComplianceOutput.
- C08 theo aggregation rule, không tính tỷ lệ SATISFIED rồi tự chọn nhãn. Không áp
  dụng một policy cho version chưa khai báo policy đó.
- C10 giữ source XOR/dedup; C11 taxonomy từ policy. Lỗi HTTP/CALL_LIMIT hướng người
  vận hành retry/tiếp tục, không được tự yêu cầu khách hàng bổ sung hồ sơ có sẵn.
- Bàn giao ca có thể kết luận và ca từ chối kết luận đúng, không chỉ happy path.

### Người 5: Orchestrator, API, FE, Review và report

- Inject implementation cụ thể vào build_services/ModuleSource. Registry chứng từ
  và verifier pin cùng context, khác đối tượng không được lọt vào request.
- Persist run QUEUED trước enqueue; duplicate key trả run cũ; API/worker dùng chung
  use case. F5 chỉ tải lại trạng thái, không tạo lại job.
- Dùng draft/report snapshot đúng run, không JOIN normalized seed để bù output thiếu.
  Completion và initial report cùng transaction; lỗi không để COMPLETED thiếu report.
- FE đọc semantic trạng thái từ contract, không suy từ tiếng Anh free text hoặc số
  lượng object. Hiển thị số được xét, confirmed, N/A, unresolved và lỗi xử lý riêng.
- Review/publish dùng latest exact revision/roles. Human decision thay effective view;
  không sửa machine finding hoặc viện dẫn review seed để duyệt run mới.
- E2E có real source/module, success/unknown/conflict/failure/retry, auth/tenant và
  export. SSE/polling, pod Ready hoặc report HTTP 200 chưa đủ nghiệm thu reasoning.

## 6. Quy tắc dữ liệu mà mọi mapper phải giữ

- Date nghiệp vụ là ISO YYYY-MM-DD; ngày thiếu độ chính xác không được tự thêm ngày.
  Timestamps chạy/review/audit là UTC có offset; UI đổi timezone khi hiển thị. Date
  thuần không bị dịch ngày chỉ vì đổi timezone. Adapter đọc ngay_danh_gia theo UTC
  stored date như code hiện tại; không mỗi module đổi theo timezone máy.
- SQL CO/KHONG/UNKNOWN → bool True/False/None. bool('KHONG') là sai. Giá trị lạ phải
  báo validation/mapping issue; không mặc định False.
- Tiền tính bằng Decimal; FE có thể nhận chuỗi, không dùng floating point để chấm
  rule. Tỷ lệ trong rule dùng fraction, không tự coi 5 là 5%.
- page_start/page_end là trang vật lý PDF 1-based, không phải số in ở footer. Quote
  offsets là chỉ số Unicode string Python trong original chunk, 0-based, [start,end).
  FE JavaScript không tự cắt bằng UTF-16 offsets rồi coi đó là xác minh backend.
- Nhiều values mâu thuẫn giữ candidates/source; không ưu tiên phụ lục, dòng đầu hoặc
  MAX(date) một cách ngầm định. ID không được dùng để suy ra thứ tự thời gian.
- Không invent C07 cho requirement version chưa resolved. Không bỏ UNKNOWN khỏi mẫu
  số coverage. N/A là có lý do không áp dụng, khác chưa hỗ trợ hoặc chưa xử lý.

## 7. Trạng thái dữ liệu sau PDF360_V4R2_20261110

| Phần | Trạng thái / owner |
|---|---|
| Scope/marker/source và runtime cùng pin | Đã dựng gói mới; người 1 phát hành ZIP/checksum và giữ DB cũ |
| Nguồn pháp luật đồng thời | Đã chốt 21 atomic families của 8 topics; người 3 JOIN thực tế, người 5 dùng topic mapping khi nhóm/đếm |
| Mẫu NĐ02/2022 và account lịch sử | Criteria/versions có nguồn và đã được chủ dự án duyệt theo snapshot hiện hành |
| NOXH | Chốt NOXH_CORE_V1; ngoài phạm vi lõi và case-specific proof vẫn cần xử lý rõ giới hạn |
| Numeric/semantic verifier | Người 4 implement theo dictionary; source references của dataset chỉ là fixtures, không thay verifier |
| Gold độc lập | Chưa được tạo bằng việc chạy engine; người 1 điều phối annotation, owner module xác nhận chất lượng |
| Drive/DB đang chạy | ZIP mới bàn giao local; snapshot đã cập nhật ở cụm local, 28 báo cáo cũ giữ nguyên. Workbook runtime mới nghiệm thu DB riêng |

Giữ UNKNOWN khi thật sự thiếu dữ kiện không là lỗi dữ liệu cần tô xanh; nhưng cũng
không chứng minh module đã đạt chất lượng. Chốt dữ liệu không tự hoàn thành code
của từng người hoặc nghiệm thu khách hàng.

## 8. Definition of Done và bộ ca ghép chung

Ma trận [handoff_acceptance.json](../contracts/handoff_acceptance.json) ghi từng
scenario, owner, mức kiểm tra và tests hiện có. Test path là điểm bắt đầu, không tự
chứng minh scenario real-provider đã được chạy. Không dùng tỷ lệ tiến độ ước lượng.

Một phần việc được bàn giao khi có implementation, mapper/persistence phù hợp chế
độ, input/output hợp lệ, pair test consumer thật và giới hạn/capabilities được ghi.
Các tests required cho bàn giao phải pass, không SKIP vì thiếu DB rồi báo hoàn tất.

Trước khi đóng integration baseline cần: một ca nội dung đủ căn cứ, một ca numeric
đúng biên/vượt biên, một ca thiếu, một ca mâu thuẫn, một ca temporal lịch sử, một ca
citation sai/không rõ và một ca lỗi provider/recovery. Với run thật phải ghi code
SHA, source/knowledge/chunk pins, model/prompt/budget và actual module_source.

Quality acceptance có expected độc lập, bao phủ đủ bốn nhãn C07/C08 và các nhãn C09
đang hỗ trợ. Các critical source/ownership, numeric boundary và promise-vs-performance
cases phải đúng toàn bộ. Macro-F1, per-class recall, Recall@K/MRR, quote accuracy,
unknown rate và processing coverage phải báo theo đúng tập annotate. Không có một
con số Macro-F1 tùy ý được gọi là chuẩn ngành hoặc thay legal review để phát hành.

Một corpus toàn UNKNOWN có thể vượt một số guard tests nhưng chưa vượt capability
acceptance nếu các ca gold đủ căn cứ phải có nhãn rõ. Một ca thiếu dữ liệu đúng thì
UNKNOWN là kết quả cần đạt, không phải lỗi cần tô xanh.

## 9. Ghép và thay đổi contracts

1. P1 công bố baseline pin; P2→P3 pair trên PDF thực; P3→P4 pair với C05/C06/C09.
2. P4→P5 pair với verifier/registry thật; P5 chạy full draft/review/export trên ca mới.
3. Sau mỗi pair sửa lỗi ngay ở owner và thêm regression; không chờ đủ năm nhánh mới chạy.
4. PR đổi input/output phải có producer + consumers + schemas/dictionary + tests;
   field trong shared contract không được sửa riêng ở nhánh một module.
5. Thay data phải release pin mới; thay code phải image/rollout riêng; lịch sử bất biến.

Gói tài liệu này không tự merge/push/rollout, không bật cluster, không sửa PDF/workbook.
Nó chốt cách làm và điều kiện nghiệm thu; mỗi owner vẫn phải implement phần việc đó.

## 10. Cơ sở kỹ thuật tham khảo

[Nguồn chính thức và cách áp dụng](../architecture/engineering_references.md) giải
thích provenance, provider verification, structure-aware chunks, legal retrieval
evaluation và quản lý rủi ro AI. Không có một layout repository hoặc một bộ công cụ
duy nhất được xem là chuẩn bắt buộc cho mọi legal AI system.

## 11. Chữ ký hàm và cách người 5 nối implementations

Schema handoff là cấu trúc validate/test; không phải mọi service nhận nguyên
envelope làm một argument. catalog.json ghi runtime_port và call_parameters thực.
CitationInput có chunks để validate nguồn; validate() chỉ nhận context/profile/
citations/knowledge, workflow kiểm chunks riêng.

| Người cung cấp | Port hiện tại | Kết quả/bên nhận |
|---|---|---|
| 2 | DocumentIntelligenceService.extract(case) | C02/chunks/C03 → 3, 4, 5 |
| 3 | ScopeResolver.resolve(context, profile, knowledge) | C04 → Temporal |
| 3 | TemporalResolver.resolve(context, profile, scope, knowledge) | C05 → Retrieval/C07/C08 |
| 3 | RetrievalService.retrieve(context, requirements, chunks, knowledge) | C06 → ObservationProvider |
| 3 | CitationValidator.validate(context, profile, citations, knowledge) | C09 → Risk/Report |
| 4 | CriterionVerificationProvider.verify(context, profile, requirements, chunks, knowledge, *, coverage=None) | Checks độc lập → LLMObservationProvider |
| 4 | EvidenceRegistryProvider.load(context, case, knowledge) | Registrations → composition và reasoning |
| 4 | ObservationProvider.observe(context, profile, requirements, retrieval, chunks, knowledge) | Observations → evaluator |
| 4 | steps_5_7.evaluate(request, knowledge) | PipelineResponse C07/C08/C10/C11 hai nhánh → 5 |
| 5 | build_run_report(draft, knowledge, module_source) | C13 machine draft → PostgresReportStore |
| 5 | AssessmentService.add_review/build_report/publish | C12 và report versions theo quyền/revision |

Người 5 sở hữu route/use case upload/case, người 2 sở hữu kiểm nguồn/extraction và
DocumentRepository, người 1 sở hữu shared storage/schema/release. Live composition
đã gọi writer trước Retrieval; không để service và workflow cùng ghi extraction.
Đổi chữ ký phải sửa Protocol + caller + fake/tests + catalog cùng PR. API và worker
dùng cùng factory; có port không tự đồng nghĩa có implementation.

Verifier hiện không nhận retrieval/case/registry argument. Nó kiểm profile.facts/
evidence và active chunks; C06 do ObservationProvider kiểm. Hai providers registry/
verification có thể dùng cùng read-only evidence repository qua constructor; người
4 implement, người 5 inject cả hai, exact case/run/hash và evidence ID/SHA. Không
query registry/C06 seed để thay dữ liệu live. Xem recipe C07 để nối dependency.

## 12. Thứ tự chạy, trạng thái và retry

Hai nhánh Scope/Temporal và Citation độc lập về nghiệp vụ; implementation hiện chạy
tuần tự trong một assessment job, chưa fan-out thành task/module. Citation được gọi
sau observations và trước evaluator hợp nhất. COMPLIANCE bắt đầu cả giai đoạn proposal;
thứ tự events không nhất thiết là thứ tự STAGES được FE liệt kê. Không tạo thêm queue
cho từng module chỉ vì sơ đồ nghiệp vụ có hai nhánh.

| Lớp trạng thái | Nguồn | Cách hiểu |
|---|---|---|
| Run | QUEUED/RUNNING/COMPLETED/FAILED | Tiến trình; COMPLETED đã có output và initial report |
| Stage | PENDING/RUNNING/COMPLETED/FAILED/SKIPPED | Tiến độ; stage complete vẫn có thể có criterion UNKNOWN |
| C07/C08 | Findings và requirement results | Nhãn pháp lý có phạm vi, khác run status |
| Diagnostic | evaluation.payload.diagnostics | CALL_LIMIT/HTTP/QUOTE_MISMATCH/missing verifier khác thiếu tài liệu |
| Review/publication | review-state, report_status/review_revision | Không suy đã duyệt từ COMPLETED/hash/seed flags |

ASSESSMENT_LLM_MAX_CALLS tính criterion calls/run; retry provider có thể thêm attempts.
Queue/recovery chỉ xử lý lỗi hạ tầng thoát ra runner; diagnostic HTTP/CALL_LIMIT đã
bắt trong provider không tự kích Celery retry. Chưa có resume từng criterion: chạy
lại hiện tạo run với idempotency key mới, giữ run/report cũ. Cùng key trả run cũ.
FE đọc status/diagnostic.code; uncertainty_reason là mô tả, không parse keyword để
đoán lỗi kỹ thuật thành thiếu hồ sơ hay vi phạm. Field mới cần handler/OpenAPI/types
cùng PR; không để UI chờ một field mà backend chưa trả.

## 13. Review gates và nguồn tài liệu có thẩm quyền

Snapshot 07/11 là SOURCE_CHECKED, giữ flags cũ và không giả human approval cho 38
criteria mới. C07 automatic review kiểm human flags của criterion/rule cụ thể. C09
hiện chỉ đặt reviewed_knowledge=true khi snapshot HUMAN_VERIFIED; vì thế C10 có thể
chặn STALE/INVALID citation risk với CITATION_PRODUCTION_GATE. C09 status vẫn đọc
được. Không đổi review label chỉ để bỏ guard. Muốn gate riêng theo legal document
thay gate toàn snapshot cần người 3/4 sửa code, người 1/5 sửa policy/tests cùng PR;
chưa coi thay đổi sản phẩm đó đã có. Phê duyệt rows mới phải release snapshot/hash mới.

36 requirements/ca là scope reference, không thay live catalog. SOURCE_SPAN_REFERENCE
không là relevance gold để chấm chính BM25 đã dựng nó. Dataset kỹ thuật không tự đóng
verifier, annotation độc lập hoặc nghiệm thu. Test schema/SQL không bảo đảm ghép lần
đầu không có bug hoặc tự chứng minh correctness pháp lý.

Quyết định hiện hành: integration_spec/policy, dictionary, catalog, playbook và guide
dataset 07/11. BRD/contracts v7.3.2/kế hoạch theo tuần/slides/PDF giải thích contracts/
changelog 05–06/11 là nguồn nghiệp vụ hoặc lịch sử; không dùng câu trạng thái cũ để
phủ định code/manifest mới. reviewed_dataset_update chỉ dành reviewed-flags release
cũ. [Biên bản rà soát](docs_alignment_changes_20261107.md) ghi từng mâu thuẫn đã sửa.

## 14. Chốt contract cho tech lead và điều kiện nhận bàn giao

PDF360_V4R2_20261110 là baseline để cả năm người dev, không phải biên bản đã
nghiệm thu mọi implementation. Dùng các quy tắc sau khi nhận PR:

1. **Cùng baseline:** PR ghi code revision, dataset/knowledge hash, module đang test,
   ca DEV và giới hạn hỗ trợ. Không dùng nhãn dataset để thay source/extraction hash.
2. **Cùng field:** dùng Pydantic models/JSON Schemas và canonical names trong
   dictionary. C02.facts/verification.facts cho phép tên linh hoạt về cấu trúc,
   nhưng không cho phép mỗi người tự đặt tên chung khác nhau. Fact mới/alias mới
   phải được tech lead cập nhật dictionary, nguồn, unit, producer/consumers và
   recipe trước khi nhận bàn giao; không chỉ thêm key vào dict rồi coi là tương thích.
3. **Cùng nghĩa:** null khác false/0; ngày dự kiến khác sự kiện thật; quote đúng
   khác predicate đã được kiểm. PR phải nêu mapping SQL→DTO, source/offset/unit,
   enum và cách xử lý unknown/conflict. Type hợp lệ chưa chứng minh nghĩa đúng.
4. **Đúng caller:** implementation thật đáp ứng port, người 5 inject vào composition
   và API/worker. Test đọc chữ ký Protocol không tự chứng minh class mới đã được nối.
5. **Có pair test:** output thật của producer phải đi thẳng qua boundary validator
   vào consumer thật. Không sửa tay payload, đổi tên field sau chạy hoặc dùng đáp án
   của consumer để làm input. Thiếu pair test thì chỉ ghi module/unit pass, chưa
   đóng handoff. Các tests cần DB phải chạy, không lấy SKIP làm PASS.
6. **Có E2E trước khi chốt tích hợp:** các ca đã định trong acceptance matrix chạy
   bằng PDF/implementations thật, cùng pins, tới draft/report/review. Fixture/schema
   pass không thay bằng chứng này. Không đợi năm người làm xong mới bắt đầu pair tests.

Ví dụ: producer cung cấp warranty_months thì consumer dùng đúng canonical key và
unit/source đã khai báo; không tự đổi thành guarantee_period. Schema có thể vẫn
chấp nhận cả hai dưới dict mở, nên cần dictionary và pair test để bắt lỗi đó.
Nếu triển khai criterion cần dữ kiện chưa được đặc tả, đó là thay đổi contract
chung phải ghi rõ trước khi merge, không để người nhận tự đoán lúc integration.

Chỉ ghi **đã chốt đặc tả** khi có baseline và rules trên. Chỉ ghi **đã nghiệm thu
handoff/E2E** khi có bằng chứng chạy thật tương ứng. Quy tắc này áp dụng cho cả năm
người, gồm phần data/tooling của tech lead; không cam kết không còn bug chỉ từ docs.
