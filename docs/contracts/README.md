# Contracts chung cho phát triển và tích hợp

> Baseline hiện hành cho DB mới: [PDF360 v4 r2 — 10/11](../guides/dataset_pdf360_v4r2_runtime_20261110.md).
> Knowledge được chủ dự án duyệt, hash `4ab2d7ea296ea908e25c09fcb6d5f073f1ebe1917678b36390f803b1c725804a`; full-catalog reference xét 323 families.
> Số liệu PDF/TEAM_CORE của revision trước bên dưới là lịch sử; literal reference mới chưa phải legal gold toàn tài liệu.


UI/export: [REPORT_PRESENTATION_V1](report_presentation.md) và
[schema](report_presentation.schema.json) tách kết luận, phạm vi và độ phủ;
projection nằm ngoài C13/hash và không thay quyết định review.

Rà soát dự thảo: [quy ước 09/11](../guides/baseline_v3_draft_review_fix_20261109.md)
và [policy máy đọc](draft_review_policy.json). C01 có review_mode/document_set_complete;
phạm vi ngoài rà soát được giữ riêng, không đổi thành tuân thủ.

Baseline dữ liệu mới: [TEAM_BASELINE_20261107](../guides/dataset_team_baseline_20261107.md). Đọc [topic mapping](legal_topic_mapping.json) và [source reference policy](source_reference_policy.json).

Biên bản thống nhất toàn docs: [docs_alignment_changes_20261107.md](../guides/docs_alignment_changes_20261107.md).
catalog.json ghi runtime_port/call_parameters và bảng operational thực, khác projections
workbook. PDF giải thích contracts là snapshot đọc tham khảo; models/schemas/spec hiện
hành có thẩm quyền cho coding. C02 catalog revision 1.1 là bổ sung fields, không phải
enum wire contract_version mới; Context envelopes vẫn 1.0.

Bắt đầu bằng [đặc tả INTEGRATION_V1](integration_spec.md) và
[từ điển dữ liệu](data_dictionary.md). BRD ở [business](../business/BRD_v1.1.pdf);
[contracts gốc v7.3.2](data_contracts_v7_3_2.md) là baseline lịch sử. Quyết định mới
được ghi rõ ở INTEGRATION_V1, không tiếp tục xem mọi ví dụ v7.3.2 là hiện trạng code.

Hướng dẫn triển khai thống nhất: [playbook năm người](../guides/parallel_development_playbook.md). Mở hỗ trợ một criterion cần có verifier/nguồn và acceptance, không chỉ DTO pass.

## 1. Các loại đặc tả

| File | Dùng để làm gì? |
|---|---|
| `C01.schema.json` … `C13.schema.json`, `X01`, `X02` | Cấu trúc record khớp runtime Pydantic |
| [module_contracts.schema.json](module_contracts.schema.json) | Envelope/input-output của từng module |
| [catalog.json](catalog.json) | Producer/consumer/cardinality/semantic rules và bảng baseline |
| [data_dictionary.json](data_dictionary.json) | Profile fields, facts numeric/units, aliases, markers, owners và gaps |
| [source_observed_extraction_baseline.md](source_observed_extraction_baseline.md) | 19 trường có trong FULL90; phần nội dung phụ thuộc mẫu; nguồn P2 bàn giao và module tiêu thụ |
| [integration_policy.json](integration_policy.json) | Execution mode, scope, review policy và taxonomy |
| [criterion_verification.schema.json](criterion_verification.schema.json), [document_read_coverage.schema.json](document_read_coverage.schema.json) | Attestation nội bộ và metadata đọc trang; không phải endpoint/public AI output |
| [handoff_acceptance.json](handoff_acceptance.json) | 19 scenario bàn giao và bằng chứng cần có; không phải báo cáo đã pass |
| [citation_provenance.schema.json](citation_provenance.schema.json) | Required context/hash/contract cho **live** C09 |
| [document_chunking_policy.json](document_chunking_policy.json) | Trial policy: source spans, structural chunks, bounded parent context và giới hạn nghiệm thu |
| [decision_rule_policy.schema.json](decision_rule_policy.schema.json) | JSON của decision rule; phân biệt kết luận về nội dung dự thảo với vi phạm thực hiện; không chạy predicate như code |
| [knowledge_applicability_policy.md](knowledge_applicability_policy.md), [schema](legal_version_policy.schema.json) | Scope fields, mốc chọn phiên bản, sự kiện thực hiện, chuyển tiếp và phân biệt revision tri thức với baseline eval |
| [database_catalog.json](database_catalog.json) | 50 bảng workbook + 6 QA; migrations còn có bảng vận hành khác |
| [OpenAPI FE–BE](../architecture/openapi.design.json) | 26 operations đã có handler; typed client frontend dùng spec này |

C01 case/source; C02 profile/facts; C03 citations; C04 scope; C05 temporal/applicable
requirements; C06 retrieval; C07 criterion; C08 requirement aggregation; C09 citation
validation; C10 risks; C11 recommendations; C12 review; C13 report. X01 pin deployment/
knowledge, X02 audit provider attempts. Chi tiết ownership H01–H24 nằm trong spec.

## 2. Dùng đúng contract

Schema validate cấu trúc, Pydantic còn có model validators. Cross-record guards kiểm
IDs/case/run/hash/quote. Consumer chỉ đòi thêm field sau khi thay đổi contract chung,
không tự tạo yêu cầu ngầm trong implementation mà producer không được biết.

C02 facts có `ten_truong` linh hoạt nên dictionary quy định canonical names/units.
Không tự alias giá bán thành mọi mẫu số numeric. Thiếu dữ kiện giữ null/UNKNOWN,
không default false/0. Review snapshot không tự duyệt output mới từ PDF.

C09 legacy source_snapshot_json vẫn là dict để đọc report/QA lịch sử. Live validator
phải dựng CitationProvenance với hash/context/hop_dong_id; C10 kiểm ownership tiếp.
C03 occurrence precise offsets/bbox vẫn là gap cần owner 2/3 chốt; không gọi grouping
citation theo văn bản là đã đo đủ occurrence recall.

## 3. Persistence và API

Live run full pipeline đọc từ workflow_runs/draft_json, report_versions và review_events.
Standalone group C dùng assessment_runs/lineage. Bảng bao_cao_danh_gia vẫn là projection
workbook có INTEGER version; live report dùng string contract + version_no riêng.
Không JOIN các bảng seed để thay kết quả mới. Chi tiết transaction/source-of-truth ở spec.

OpenAPI thiết kế giữ operationId ổn định cho FE; backend `/openapi.json` cho schema
runtime, Swagger `/docs`. Auth thực tế hỗ trợ session cookie và Bearer khi AUTH_MODE=on;
off là dev actor. Mô tả/metadata spec không thay authorization handler. FE không gửi
actor/tenant để tự quyết quyền, không gửi C05/C06 cho endpoint chạy assessment.

## 4. Thay đổi và nghiệm thu

Cùng một PR cập nhật model + schema + catalog/dictionary/semantics + producer/consumer
+ tests; nếu đổi HTTP thì OpenAPI + generated frontend types. Alembic riêng cho DB.
Tool sinh cũ không cần khôi phục; đặc tả được quản lý trong repo và kiểm tra bằng tests.

```bash
pytest -q -c backend/pyproject.toml backend/tests/contract
python -m devtools.integration_audit --output data/private/integration_audit
npm --prefix frontend run gen:api
npm --prefix frontend run build
```

Audit DB chỉ đọc snapshot pin; private CSV có một dòng mỗi criterion. Các binding
semantic/branch chưa thể chứng minh từ catalog được ghi là cần owner review, không
sinh gold labels bằng keyword. Tests contract/handoff không thay eval chất lượng.

## 5. Rà toàn văn và bổ sung evidence cho C06

`document_review.schema.json` là chứng từ nội bộ của backend, không phải contract
HTTP mới. `DocumentReviewArtifact` khóa case/run/knowledge hash, source SHA,
extraction version, hash từng chunk, tất cả batch và ma trận batch × criterion.
Validator runtime kiểm coverage và kết luận khớp ma trận; JSON Schema chỉ kiểm shape.

Workflow gọi `retrieval_refinement.refine(...)` sau truy xuất ban đầu, trước
`validate_retrieval` và C07. Chỉ chunk thuộc extraction hiện hành được bổ sung làm
C06 FINAL/selected. Phải **trả danh sách C06 mới**; sửa một bản deepcopy trong
`observations.observe` không thay đổi C06 mà evaluator dùng.

`ABSENT` trên top-K không chứng minh vắng toàn tài liệu. Chỉ khi mọi chunk và mọi
criterion trong lượt rà đã có kết quả, không có UNCERTAIN cho criterion đó, mới có
`absence_verified`. Chứng từ lưu tại `artifact://evidence/<sha>.json`; excerpt là
literal string ở `/conclusion_text/<criterion_id>`, không phải quote hợp đồng giả.
Kết quả vẫn là MACHINE DRAFT và `review_status=PENDING`.

`assessment_disposition` trong C08 snapshot là thông tin vận hành: ASSESSED,
NEEDS_EVIDENCE, LEGAL_SCOPE_UNRESOLVED, NOT_TRIGGERED. NOT_TRIGGERED chỉ dùng khi tất
cả criterion bắt buộc được loại trừ hợp lệ theo điều kiện riêng. Đây không phải
status pháp lý thứ năm: bốn status và AGG_CAN_HO_V1 giữ nguyên, FE giải thích riêng.


Bổ sung runtime 08/11: C02 v1.2 thêm boolean nullable `co_thoa_thuan_dat_coc`;
không suy thiếu thỏa thuận từ việc chưa thu tiền. LegalVersionPolicy thêm liên kết
family lịch sử có nguồn. Revision catalog clone base, không đổi snapshot lịch sử.
C13 có display statuses theo disposition; raw C07/C08 và policy AGG_CAN_HO_V1 giữ nguyên.
[Xem quy trình và lệnh áp dụng](../guides/complete_runtime_alignment_20261108.md).

Policy bổ sung: [Định danh viện dẫn C09 V2](citation_identity_policy.json), giữ C03 quan sát gốc và provenance của cách phân giải.
