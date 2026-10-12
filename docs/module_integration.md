# Nối các module theo BRD v1.1

## Cấu trúc và điểm nối

Giữ backend tại `app/`; `api/` xử lý HTTP, `contracts/` giữ Pydantic schemas, `modules/` giữ nghiệp vụ, `application/` điều phối, `infrastructure/` hiện thực storage/provider adapters. Frontend skeleton dùng feature folders, chưa chọn framework.

| BRD | Module | Consumer contract / implementation cần cung cấp |
|---|---|---|
| 1 | `intake` | `IntakeService.register`: C01 case/source/deployment pin |
| 2 | `document_intelligence` | `DocumentIntelligenceService.extract`: C02 profile + chunks + C03 citations |
| 3A | `scope_resolver` | `ScopeResolver.resolve`: C04 checklist; không đọc contract citations |
| 3A | `temporal_resolver` | `TemporalResolver.resolve`: C05; giữ field scope thuộc Scope Resolver |
| 3B | `citation_validation` | `CitationValidator.validate`: C09; relevant/current status riêng |
| 4 | `retrieval` | `RetrievalService.retrieve`: C06 per criterion/chunk; không kết luận legal finding |
| 5 | `compliance_reasoning` | `ObservationProvider.observe` + engine `reason`: C05/C06/knowledge → C07 |
| 5 | `rule_aggregation` | Engine `aggregate`: C05/C07/knowledge → C08 |
| 6 | `risk` | Engine `aggregate_risks`: C07/C09 → C10 |
| 7 | `recommendation` | Engine `recommend`: C10/context/templates → C11 |
| 8 | `human_review` | `HumanReviewService` + `ReviewStore`: append-only C12 events |
| 9 | `reporting` | `ReportService` + `ReportStore`/`ReportExporter`: C13 versions/export |

Các services bước 1–4, 8–9 và Knowledge Curation hiện là `Protocol`, chưa có concrete implementation. Ports mô tả input/output để team lập trình độc lập; chúng không gọi LLM/OCR hay tạo dữ liệu giả.

## Skeleton điều phối draft

`app/application/pipelines/draft_assessment.py` cung cấp wiring executable khi tất cả upstream adapters được inject:

```python
from app.application.pipelines.draft_assessment import DraftAssessmentWorkflow, DraftModules

modules = DraftModules(
    intake=intake_adapter,
    documents=document_intelligence_adapter,
    scope=scope_adapter,
    temporal=temporal_adapter,
    retrieval=retrieval_adapter,
    citations=citation_adapter,
    observations=verified_observation_adapter,
)
draft = DraftAssessmentWorkflow(modules, knowledge_snapshot).evaluate(case_c01, context)
```

Các tên adapters trong ví dụ là implementations team phải cung cấp; chưa có factory full-system mặc định. `draft` là `AssessmentDraft`, gồm C01, profile/chunks/citations, C04/C05/C06 và `evaluation` C07–C11. Workflow giữ case/deployment pin và checksum knowledge; không ghi DB hoặc tự duyệt/publish report. Caller chọn persistence qua ports sau khi kiểm tra authorization.

Luồng Applicable Law chỉ nhận profile/scope/knowledge. Citation Validator nhận citations/profile/knowledge riêng, kết quả hội tụ tại Risk. Thay citation status không được làm thay checklist hoặc compliance results. Checklist rỗng bị từ chối vì chưa biểu diễn rõ scope/coverage; chưa hỗ trợ full-assessment không có requirement.

## Refactor bước 5–7

- `core/validation.py` kiểm tra context snapshot, C05 và C09 độc lập. Request reasoning/pipeline tái sử dụng các helpers.
- `application/validation.py` kiểm tra C07/C10 tại consumer boundaries. C07 legal basis/decision rule phải khớp knowledge snapshot. C10 rule/catalog/branch/criterion/version/severity/legal basis phải khớp; không cho downstream tự nâng severity hoặc đổi nguồn risk.
- HTTP routes gọi validation/services; không chứa rule pháp lý. Các imports/payload/URL cũ vẫn có compatibility facade.
- `contracts/workflow.py` là checkpoint draft nội bộ để ghép module, không tạo thêm bảng DB cho logical contract.

## Adapter và ownership

`CriterionProposalProvider` chỉ trả proposed finding/explanation/quotes. `ObservationProvider` ghép proposal với facts và gates do backend xác minh. Provider không sở hữu scope/source/absence/coverage gates. Không bật tất cả gates chỉ vì LLM trả confidence cao.

`SourceStorage`/`DocumentReader` giữ source hash, trang, phương pháp TEXT/OCR và readability. `EvidenceIndex`/`EvidenceReranker` giữ scope hợp đồng/index version, không trả VIOLATED/MISSING. `LlmAuditSink` chỉ ghi X02 cho provider calls thật.

Review/report cần `AccessPolicy`, append-only C12, effective reviewed result và publish authorization. Tạo folder/schema/interface chưa phải đã triển khai phân quyền hoặc acceptance criteria human review/report.

## Kiểm tra

`tests/test_draft_workflow.py` inject adapters giả lập để kiểm tra orchestration, pins, ownership và branch independence. Đây là test wiring, không phải E2E OCR/LLM production.

`tests/test_downstream_boundaries.py` kiểm tra API từ chối C07/C10 sai provenance, duplicate IDs hoặc source ngoài checklist. `tests/test_architecture.py` giữ business modules độc lập với HTTP/SQLite/provider adapters.

E2E HTTP thực cho engines bước 5–7:

```bash
DATABASE_PATH=data/private/e2e.sqlite3 uvicorn app.main:create_app --factory
# Terminal khác, từ thư mục repo:
python scripts/e2e_steps_5_7.py
```

Quality evaluation theo BRD mục 13 có skeleton tại `evals/`; chưa có gold datasets/metric runners. Test software pass không thay thế đánh giá legal/model quality.
