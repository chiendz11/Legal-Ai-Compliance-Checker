# Đặc tả tích hợp cho năm người — INTEGRATION_V1

> Baseline hiện hành cho DB mới: [PDF360 v4 r2 — 10/11](../guides/dataset_pdf360_v4r2_runtime_20261110.md).
> Knowledge được chủ dự án duyệt, hash `4ab2d7ea296ea908e25c09fcb6d5f073f1ebe1917678b36390f803b1c725804a`; full-catalog reference xét 323 families.
> Số liệu PDF/TEAM_CORE của revision trước bên dưới là lịch sử; literal reference mới chưa phải legal gold toàn tài liệu.


Bổ sung vận hành 09/11: [điều kiện dự thảo, mẫu số bảo trì và mốc khai báo C01](../guides/remaining_verification_alignment_20261109.md). Dùng cùng [draft_review_policy.json](draft_review_policy.json); không thay C05 bằng context của run khác hoặc suy NO_MATCH thành đáp ứng.

Bổ sung 09/11: [rà soát dự thảo v3](../guides/baseline_v3_draft_review_fix_20261109.md)
chốt C01 review_mode/document_set_complete, receipt C05, verifier source-only và
OUTSIDE_REVIEW_SCOPE ở C07/C08/C13. Không dùng PDF để tự đổi phạm vi hoặc phê duyệt.

Bổ sung 07/11: [TEAM_BASELINE_20261107](../guides/dataset_team_baseline_20261107.md) chốt atomic source families, NOXH core và scope tham chiếu 36 requirements/ca. Schema C05/C07/C08 không đổi; không hardcode 10 families cũ.

Cập nhật 07/11/2026. Đây là quyết định tích hợp hiện hành, bổ sung contracts gốc
v7.3.2; không sửa lại luật hoặc biến dữ liệu thiếu thành đã biết. Đọc cùng
[từ điển dữ liệu](data_dictionary.md), [policy JSON](integration_policy.json),
[catalog](catalog.json) và [bàn giao nhóm](../guides/team_onboarding_and_next_steps.md).

Bổ sung 06/11: [policy scope/temporal của tri thức](knowledge_applicability_policy.md)
chốt marker và schema metadata; revision workbook đi kèm giữ runtime/QA lịch sử,
chưa tự thay dataset pin hoặc triển khai DB.

Bổ sung 07/11: [baseline extraction theo FULL90 thực tế](source_observed_extraction_baseline.md)
chốt tập dữ liệu đã có trong PDF và cách module tiêu thụ. Giữ nguồn cố định;
không tạo thêm nội dung để ép đủ field, không hạ checklist khi nguồn chưa đủ.

Bổ sung 08/11: [rà toàn văn và C06 refinement](../guides/hd360_followup_verification_20261108.md) chốt coverage proof, nguồn bất biến và operational disposition; bốn status C08 giữ nguyên.

## 1. Phương án đã chọn và nguồn có thẩm quyền

Giữ modular monolith: một backend image, API và Celery worker chạy các tiến trình
riêng; Beat một scheduler; PostgreSQL lưu trạng thái, Redis chuyển job, storage giữ
bytes nguồn. Các module giao tiếp bằng hàm Python và DTO, không thêm HTTP service
cho từng bước. Người 5 compose; module sở hữu thuật toán/repository của mình.

| Cần quyết định | Nguồn chính |
|---|---|
| Nghiệp vụ, acceptance | BRD; quyết định bổ sung tại tài liệu này |
| Field/enum/cấu trúc module | Models `shared/contracts/` + JSON Schema tương ứng |
| Ý nghĩa, nguồn, owner, điều kiện sử dụng | Tài liệu này + dictionary + catalog |
| DB thật | Alembic migrations; catalog workbook không phải toàn bộ DB ứng dụng |
| Pháp luật/rules của run | Knowledge snapshot đúng SHA, không đọc bảng mới nhất thay snapshot |
| PDF, annotations, split | Dataset release + manifest/checksum; không dùng expected TEST để tuning |
| FE ↔ BE | `architecture/openapi.design.json`, đối chiếu `/openapi.json` khi triển khai |

Contract hợp lệ gồm: cấu trúc + quan hệ IDs + quyền/tenant + nguồn + run/hash + điều
kiện nghiệp vụ. JSON Schema pass không chứng minh tất cả các điều kiện này.

## 2. Phân công và các điểm bàn giao

P là người chủ trì, phối hợp không đồng nghĩa cùng sửa mọi file. Các tên module là
ranh giới code, không phải bằng chứng ai viết commit hoặc tỷ lệ hoàn thành.

| ID | Từ → đến | Dữ liệu / điều kiện bàn giao | P và phối hợp |
|---|---|---|---|
| H01 | Dataset → dev DB | DEV/VAL đúng ZIP/workbook hash; MASTER evaluator; TEST input riêng | 1; cả nhóm kiểm pin |
| H02 | Release → API/worker | Migration + snapshot tồn tại trước khởi chạy; restart reader khi đổi pin | 1+5 |
| H03 | Upload/storage → Documents | C01, đúng tenant, bytes đúng SHA; URL lỗi dừng, không replay ngầm | 2+5; 1 storage |
| H04 | Documents → writer | C02/chunks/C03 có nguồn; commit extraction trước Retrieval | 2; 5 gọi writer |
| H05 | Documents → Scope | Typed profile/subjects; field catalog chưa hỗ trợ phải UNKNOWN | 2+3; 1 catalog |
| H06 | Scope → Temporal | C04 không mất requirement; Temporal không sửa scope-owned fields | 3 |
| H07 | Markers/catalog → Temporal | Phân biệt ngày dự kiến/thực tế; version ứng viên không phải resolved | 1+3; 2 nguồn |
| H08 | C05 → Retrieval | Đúng version/criterion; không truy theo citations để thay checklist | 3 |
| H09 | Chunks/DB → Retrieval | Section paths/fact evidence chỉ từ active extraction/chunk IDs | 2+3; 5 thứ tự |
| H10 | C06 → C07 | selected FINAL cùng case/run/criterion/contract; quote nguyên bản | 3+4 |
| H11 | Facts/receipts → verifier | Canonical names/units; semantic review riêng; không lấy facts từ AI tự duyệt | 4; 2 nguồn, 3 scope |
| H12 | Verifier → provider C07 | CriterionVerification pin đúng criterion/case/run/hash; inject trước AI | 4 cung cấp; 5 nối |
| H13 | Proposal → C07 | Quote/schema/predicate/gates; lỗi budget/provider không thành vi phạm | 4 |
| H14 | C07 + C05 → C08 | Rule aggregation; N/A loại có lý do; unresolved giữ INSUFFICIENT | 4; 3 trạng thái |
| H15 | C03 → C09 | Raw/normalized + vị trí, signing context; name-only chưa tự định danh duy nhất | 2+3 |
| H16 | C09 → C10 | Live provenance có context/hash/hop_dong_id; finding review khác knowledge review | 3+4; 5 tích hợp |
| H17 | C07/C09 → C10 | Giữ hai nhánh, source XOR, dedup; UNKNOWN là verification | 4; 3 citation |
| H18 | C10 → C11 | Link risk instance; taxonomy verification/corrective thống nhất | 4+5 |
| H19 | Workflow → report | C13 lấy output cùng run; giữ diagnostics, nguồn module và checklist thực tế | 5; 2–4 cung cấp |
| H20 | Run → initial report | COMPLETED và report đầu tiên commit cùng transaction | 5 |
| H21 | Reviewer → report | C12 append-only, đúng target hash/revision; không sửa machine output | 5 |
| H22 | Report → publish | REVIEW_ALL_FINDINGS_V1; mọi target có CONFIRM/OVERRIDE, COMMENT chưa đủ | 5; cả nhóm nghiệm thu |
| H23 | API → FE | Typed client, role/tenant ở BE; null/UNKNOWN/lỗi kỹ thuật hiển thị đúng nghĩa | 5; 2–4 giải thích output |
| H24 | CI/image/GitOps/DB → môi trường | Bốn bước độc lập; image đúng SHA, nhánh Argo đúng, DB update riêng | 1+5 |

## 3. Nguồn dữ liệu và chế độ chạy

| ASSESSMENT_MODULES | Hành vi |
|---|---|
| `modules` | Đọc bytes thật qua upload/cache/HTTP(S), kiểm SHA và chạy Documents; không fallback QA |
| `modules_di_reference` | DEV/EVAL: khi chưa có local bytes thì dùng C02/chunks/C03 reference; phần sau chạy thật; nhãn MODULES_DI_REFERENCE |
| `reference` | QA replay toàn luồng; nhãn REFERENCE_REPLAY; không phải inference thật |
| `none` | Báo chưa cấu hình, không tạo kết quả giả |

PDF khách hàng dùng `modules`. Failure đọc URL, scan chưa OCR, format chưa hỗ trợ
phải hiện lỗi. Upload chấp nhận DOCX để lưu nguồn không đồng nghĩa parser DOCX đã có.
Mỗi run audit lưu nguồn module; không lấy reference để thay kết quả upload thất bại.

## 4. Phạm vi checklist và mốc thời gian

Live mặc định xét **toàn catalog trong snapshot đã pin**, baseline 07/11 có 323 families.
Reference corpus cũ dùng `TEAM_CORE_REFERENCE_V1`: 36 atomic requirements/ca, ID cụ thể
trong ASSESSMENT_SCOPE.json. Dùng legal_topic_mapping.json để nhóm chủ đề nhiều nguồn;
không JOIN/dedup bằng parent ID cũ. Đánh giá metric chỉ trên cùng tập family đã annotate;
phần ngoài tập đó phải báo coverage riêng. Không tự giảm checklist để tăng metric.
C13 lưu danh sách requirement_ids thực tế, không chỉ ghi tên một profile mơ hồ.

C04 MATCH không đồng nghĩa C05 CONFIRMED. C05 chỉ CONFIRMED khi scope MATCH, version
RESOLVED và có relevant date. Có version ID khi UNKNOWN chỉ là ứng viên; FE phải ghi
“ứng viên”. NOT_APPLICABLE được giữ trong checklist và loại có lý do khỏi C08.

Interval hiện tại là `[hieu_luc_tu, hieu_luc_den)`. Không chọn version đầu tiên khi
chồng lấn. Không lấy ngày ký thay ngày thu tiền. Catalog marker chưa có mapping,
coverage lịch sử thiếu hoặc nhóm phiên bản chưa phân định: UNKNOWN kèm reason.
Metadata LEGAL_VERSION_POLICY_V1 trong snapshot là policy version mới; DEFAULT_MARKER_TYPES/
DEFAULT_FAMILY_EVENTS là fallback cho legacy, không được ghi đè policy typed đã pin.
Thay policy cần nguồn và regression biên ngày; người 1 sở hữu catalog, người 3 sở hữu resolver; không đổi snapshot cũ.

## 5. Dữ kiện, xác minh và C07

Knowledge HUMAN_VERIFIED xác nhận snapshot đã duyệt; SOURCE_CHECKED chỉ xác nhận
đã kiểm nguồn, không giả định human review của criteria mới. Cả hai không xác nhận ngày còn null,
giá bị mâu thuẫn, output mới của parser hoặc kết luận mới của AI. SHA xác nhận bytes;
quote/offset xác nhận attribution; chúng chưa chứng minh toàn bộ predicate pháp lý.

Đăng ký chứng từ ngoài dùng `EvidenceRegistryProvider.load(context, case, knowledge)` riêng, trả ExternalEvidenceRegistration đúng context và hash. Composition kiểm pin trước khi truyền cùng registry cho C07 và evaluator. Chỉ provider đã kiểm bytes/nguồn mới được đặt verified; loader không tự tin một URL.

Người 4 implement `CriterionVerificationProvider.verify(context, profile,
requirements, chunks, knowledge, *, coverage=None)`. Metadata DocumentReadCoverage được truyền từ cùng extraction; không suy coverage/absence chỉ từ số chunks. Người 5 inject vào `build_services` hoặc
`IntegratedModulesSource`; không tạo default verifier bật mọi gate. Composition hiện
inject SourceFactVerifier cho quote/fact checks cơ bản. Nếu khởi tạo source trực tiếp
mà thiếu provider, diagnostic VERIFICATION_PROVIDER_NOT_CONFIGURED vẫn được giữ.
SYNTHETIC_SCENARIO_PATH chỉ bật các attestations của PDF/snapshot/criterion khớp
[policy đồ án](../guides/synthetic_evidence_and_inference_fixes_20261107.md); audit và
export giữ evidence_mode=SYNTHETIC, không sửa mức human review của knowledge.

```python
from legal_checker.api.dependencies import build_services
from legal_checker.core.config import Settings
from legal_checker.main import create_app

# my_provider là implementation của người 4, kiểm tra thật facts/nguồn/điều kiện.
services = build_services(Settings.from_env(), verification_provider=my_provider)
app = create_app(services=services)
```

Facts AI đề xuất không tự thành verified facts. Numeric dùng Decimal, đơn vị/mẫu số
và branch/target được xác nhận riêng. Ngoại lệ, sự kiện thực hiện nghĩa vụ, chứng từ
ngoài và absence không được suy ra chỉ từ top-K hoặc một lời hứa trong hợp đồng.
MISSING cần coverage/absence/mandatory; retrieval rỗng không tự là MISSING.

Ngân sách tính theo criterion calls; retry có thể tạo nhiều provider attempts hơn.
CALL_LIMIT/OFFLINE_NO_CLIENT/HTTP error/QUOTE_MISMATCH được giữ ở diagnostics. Scope
và version đã biết không bị xóa chỉ vì chưa gọi AI; các gate khác không tự được bật.

## 6. Live C09 provenance và tương thích lịch sử

Live producer phải validate `CitationProvenance` và JSON Schema
`citation_provenance.schema.json`. Bắt buộc `knowledge_snapshot_sha256`, `context`,
`hop_dong_id`; hash trong context phải khớp. C10 kiểm tiếp case/run/contract.
C09 record legacy vẫn đọc được với dict cũ để không viết lại report/QA lịch sử;
thiếu pin không được coi là live handoff đủ điều kiện tạo STALE/INVALID risk.

`reviewed_knowledge` phản ánh snapshot; `finding_checks_verified` phản ánh kiểm tra
finding. Domain UNKNOWN không được thành VALID. Policy hiện hành
[C09_CATALOG_IDENTITY_V2](citation_identity_policy.json) cho phép số hiệu, tên+năm
khớp duy nhất, hoặc dẫn chiếu cùng tên tới số hiệu tường minh duy nhất trong cùng
hợp đồng. Tên chung thiếu năm/số và không có anchor vẫn UNKNOWN; không chọn bản
đang có hiệu lực chỉ để giải quyết identity. C03 raw/normalized giữ nguyên dữ kiện
quan sát; C09 ghi rõ cách định danh và ID citation làm anchor.

SOURCE_CHECKED không làm reviewed_knowledge=true: producer hiện chỉ gán true cho
snapshot HUMAN_VERIFIED. Vì vậy C09 có thể có status nhưng C10 chặn citation risk
khẳng định bằng CITATION_PRODUCTION_GATE; không nhầm đây là lỗi mất C09 khi nối module.

## 7. Persistence và nguồn đọc thật

| Loại dữ liệu | Nguồn đọc/ghi có thẩm quyền |
|---|---|
| Baseline dev/eval | Normalized workbook rows và qa.artifacts; không coi là live output |
| Extraction thật | DocumentRepository ghi facts/chunks/citations/markers đồng bộ; profile bảng đơn giữ mặc định nếu đã có |
| Run full pipeline | runtime.workflow_runs.draft_json là snapshot C01–C11 của đúng run; không JOIN baseline thay live output |
| Standalone group C | Store: runtime.assessment_runs + normalized outputs + lineage; khác workflow_runs |
| Report thật | runtime.report_versions, immutable versions; bao_cao_danh_gia là workbook projection chưa ghi từ live writer |
| Review thật | runtime.review_events; nhat_ky_review có mirror; thứ tự/revision lấy review_events |
| Knowledge | knowledge.knowledge_snapshots; pin và checksum; không sửa snapshot |

Không phải module nào cũng phải ghi output vào bảng workbook trước khi gọi module
kế tiếp. Workflow truyền DTO trong bộ nhớ, run snapshot giữ kết quả; Documents phải
lưu trước vì Retrieval hiện đọc metadata DB. Re-extraction giữ IDs/version mới;
Retrieval giới hạn metadata vào các chunk IDs đang thực sự được truyền. Profile đơn
trong DB không được dùng thay profile DTO của extraction mới của run.

Run COMPLETED không khẳng định hết mọi criterion đã được AI xử lý. API/worker dùng
cùng runner; initial report và completion được commit nguyên tử. Redis at-least-once,
không cam kết exactly-once; claim/lease và idempotency chống lặp theo thiết kế hiện tại.

## 8. Report, FE và phát hành

C13 ghép kết quả, không chạy thêm một LLM để thay kết luận các bước trước. Tách
compliance/citation/verification risks. Số checklist được xét khác số xác nhận áp dụng.
VERIFY, VERIFY_REFERENCE, REQUEST_VERIFICATION, REQUEST_EVIDENCE thuộc xác minh.
Diagnostic kỹ thuật không được gọi là vi phạm pháp lý. C11 template chưa phân biệt
đủ thông điệp retry và bổ sung hồ sơ: owner 4+5 còn phải nghiệm thu nội dung; không
sửa template knowledge âm thầm bằng đổi nhãn frontend.

**REVIEW_ALL_FINDINGS_V1:** mọi target reviewable C07/C08/C09/C10/C11 phải có quyết
định CONFIRM hoặc OVERRIDE. COMMENT không phê duyệt; REJECT/REQUEST_MORE_EVIDENCE
chặn. Reviewer được CONFIRM kết luận UNKNOWN với giới hạn được chấp nhận; không
cần biến nó thành SATISFIED. Publish đúng revision và quyền; report mới bất biến,
machine output giữ nguyên. Auth off chỉ dành local dev; phát hành khách hàng cần
auth on, quản lý tài khoản/tenant và nghiệm thu quyền thực tế.

## 9. Tách các mức nghiệm thu

| Mức | Bằng chứng | Không thay thế cho |
|---|---|---|
| Schema | DTO/JSON Schema hợp lệ | Pháp lý đúng, evidence đúng |
| Module | Tests rule/parser/retrieval độc lập | Tích hợp thật |
| Handoff | Producer thật → consumer thật, IDs/metadata/provenance đúng | Accuracy toàn corpus |
| E2E kỹ thuật | PDF → real modules → run/report, queue/recovery | Quality luật/OCR/LLM |
| Eval chất lượng | Tập annotate độc lập, split cố định, metric theo phạm vi | Customer release |
| Release | Auth/review/rollback/backup + image/DB pins và vận hành được nghiệm thu | Production HA/hiệu năng chưa đo |

Những catalog gaps trong audit phải đóng bằng dữ liệu/policy có nguồn và PR owner,
không được ghi “đã xử lý” chỉ vì đã có guard UNKNOWN. Rà soát này không tự xác nhận
mọi luật/nhãn pháp lý đúng hoặc mọi PDF đã có đầy đủ fields.

## 10. Quy trình bàn giao đã chốt ngày 06/11

[Playbook năm người](../guides/parallel_development_playbook.md) quy định rõ scope,
input theo từng module, mapping primitive/offset/timezone, write ownership, data
blockers và Definition of Done. [Ma trận nghiệm thu](handoff_acceptance.json) là
requirements, không phải run results. Producer pass unit/schema nhưng consumer chưa
nhận được output thật thì chưa đóng handoff.

[Recipe C07](../modules/criterion_verification_guide.md) phân loại bảy criterion types,
control facts và numeric branches. [Các nguồn tham khảo](../architecture/engineering_references.md)
là cơ sở kỹ thuật, không tự chứng nhận mọi logic pháp lý hoặc mọi ca corpus.
