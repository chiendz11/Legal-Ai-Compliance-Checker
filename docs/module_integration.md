# Nối các module theo BRD v1.1

## Cấu trúc và điểm nối

Backend tại `backend/src/legal_checker/`; `api/` xử lý HTTP, `shared/contracts/` giữ schemas, `modules/` giữ nghiệp vụ và repositories, `workflows/` điều phối, `core/` và `shared/` giữ công cụ kết nối dùng chung. Frontend skeleton dùng feature folders, chưa chọn framework.

| BRD | Module | Consumer contract / implementation cần cung cấp |
|---|---|---|
| 1 | `documents/intake.py` | `IntakeService.register`: C01 case/source/deployment pin |
| 2 | `documents` | `DocumentIntelligenceService.extract`: C02 profile + chunks + C03 citations |
| 3A | `applicable_law/scope_resolver.py` | `ScopeResolver.resolve`: C04 checklist; không đọc contract citations |
| 3A | `applicable_law/temporal_resolver.py` | `TemporalResolver.resolve`: C05; giữ field scope thuộc Scope Resolver |
| 3B | `citation_validation` | `CitationValidator.validate`: C09; relevant/current status riêng |
| 4 | `retrieval` | `RetrievalService.retrieve`: C06 per criterion/chunk; không kết luận legal finding |
| 5 | `compliance` | `ObservationProvider.observe` + engine `reason`: C05/C06/knowledge → C07 |
| 5 | `compliance/requirement_aggregator.py` | Engine `aggregate`: C05/C07/knowledge → C08 |
| 6 | `risks` | Engine `aggregate_risks`: C07/C09 → C10 |
| 7 | `recommendations` | Engine `recommend`: C10/context/templates → C11 |
| 8 | `reviews` | `HumanReviewService` + `ReviewStore`: append-only C12 events |
| 9 | `reports` | `ReportService` + `ReportStore`/`ReportExporter`: C13 versions/export |

Các services bước 1–4, 8–9 và Knowledge Curation có interfaces `Protocol`. Bước 9 có helper `reports/builder.py` dựng C13 draft; export/persist/publish vẫn chưa triển khai. Ports mô tả input/output để team lập trình độc lập; chúng không gọi LLM/OCR hay tạo dữ liệu giả. [Hướng dẫn nhóm](huong_dan_trien_khai_module_sau_seed.md) mô tả query/mapping từ DB và tests từng phần.

## Skeleton điều phối draft

`backend/src/legal_checker/workflows/assessment_workflow.py` cung cấp wiring executable khi tất cả upstream adapters được inject:

```python
from legal_checker.workflows.assessment_workflow import DraftAssessmentWorkflow, DraftModules

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

Các tên adapters trong ví dụ là implementations team phải cung cấp; chưa có factory full-system mặc định. `draft` là `AssessmentDraft`, gồm C01, profile/chunks/citations, C04/C05/C06, `citation_findings` C09 và `evaluation` C07–C11. Workflow giữ case/deployment pin và checksum knowledge; không ghi DB hoặc tự duyệt/publish report. Caller chọn persistence qua ports sau khi kiểm tra authorization.

Luồng Applicable Law chỉ nhận profile/scope/knowledge. Citation Validator nhận citations/profile/knowledge riêng, kết quả hội tụ tại Risk. Thay citation status không được làm thay checklist hoặc compliance results. Checklist rỗng bị từ chối vì chưa biểu diễn rõ scope/coverage; chưa hỗ trợ full-assessment không có requirement.

## Refactor bước 5–7

- `shared/validation.py` kiểm tra context snapshot, C05 và C09 độc lập. Request reasoning/pipeline tái sử dụng các helpers.
- `modules/compliance/grounding_validator.py` kiểm tra C07 và `modules/recommendations/validator.py` kiểm tra C10 tại consumer boundaries. C07 legal basis/decision rule phải khớp knowledge snapshot. C10 rule/catalog/branch/criterion/version/severity/legal basis phải khớp; không cho downstream tự nâng severity hoặc đổi nguồn risk.
- HTTP routes gọi validation/module services; không chứa rule pháp lý. Imports dùng module sở hữu. Reasoning nhận `CriterionReasoningInput`; pipeline nhận `Steps57Input` riêng.
- `shared/contracts/workflow.py` là checkpoint draft nội bộ để ghép module, không tạo thêm bảng DB cho logical contract.

## Adapter và ownership

Imports theo module sở hữu:

| Chức năng | Module canonical |
|---|---|
| Pipeline `evaluate` | `legal_checker.workflows.steps_5_7` |
| Reasoning `reason` | `legal_checker.modules.compliance.criterion_reasoner` |
| Numeric rules `numeric_finding` | `legal_checker.modules.compliance.numeric_rules` |
| Aggregation `aggregate` | `legal_checker.modules.compliance.requirement_aggregator` |
| Risk engines | `legal_checker.modules.risks.aggregator` |
| Recommendation `recommend` | `legal_checker.modules.recommendations.generator` |
| Downstream validation | `legal_checker.modules.compliance.grounding_validator` / `legal_checker.modules.recommendations.validator` |
| Request/context validation | `legal_checker.shared.validation` |
| Stable IDs | `legal_checker.shared.ids` |

Khi gọi engines trực tiếp, truyền `Context` cùng requirements/citations theo chữ ký hiện tại; pipeline trong workflows chịu trách nhiệm ghép các inputs này. Contracts được import từ `shared/contracts/reasoning.py`, `shared/contracts/pipeline.py`, `shared/contracts/risk.py` và các owning modules khác. Knowledge reader ở `modules/legal_knowledge/repository.py`; run store ở `modules/assessments/repository.py`; kết nối dùng chung ở `core/postgres.py`.

```python
from legal_checker.workflows.steps_5_7 import evaluate
from legal_checker.modules.compliance.requirement_aggregator import aggregate

response = evaluate(pipeline_request, knowledge)
results = aggregate(context, knowledge, criterion_results, applicable_requirements)
```

Factory dùng một cấu hình `Settings` rõ ràng hoặc đọc DATABASE_URL khi không truyền settings:

```python
from legal_checker.core.config import Settings
from legal_checker.main import create_app

api = create_app(settings=Settings.from_env())
```

`api/dependencies.py:build_services` tạo knowledge/run store và được `main.create_app()` gọi khi chưa inject Services. `main.py` tạo FastAPI và router. Trong tests có thể inject `Services` bằng `create_app(settings=settings, services=services)` để thay storage mà không tạo DB mặc định.

Các clients gọi riêng Reasoning gửi `contract_name=CriterionReasoningInput` và payload C05/C06/chunks/observations, theo `examples/reasoning.json`. C09/citations được gửi tới Risk hoặc pipeline; Reasoning từ chối payload pipeline với HTTP 422. Script E2E xây từng request đúng contract và đối chiếu output với pipeline.

`CriterionProposalProvider` chỉ trả proposed finding/explanation/quotes. `ObservationProvider` ghép proposal với facts và gates do backend xác minh. Provider không sở hữu scope/source/absence/coverage gates. Không bật tất cả gates chỉ vì LLM trả confidence cao.

`SourceStorage`/`DocumentReader` giữ source hash, trang, phương pháp TEXT/OCR và readability. `EvidenceIndex`/`EvidenceReranker` giữ scope hợp đồng/index version, không trả VIOLATED/MISSING. `LlmAuditSink` chỉ ghi X02 cho provider calls thật.

Review/report cần `AccessPolicy`, append-only C12, effective reviewed result và publish authorization. Tạo folder/schema/interface chưa phải đã triển khai phân quyền hoặc acceptance criteria human review/report.

## Kiểm tra

`backend/tests/integration/test_draft_workflow.py` inject adapters giả lập để kiểm tra orchestration, pins, ownership và branch independence. Đây là test wiring, không phải E2E OCR/LLM production.

`backend/tests/contract/test_downstream_boundaries.py` kiểm tra API từ chối C07/C10 sai provenance, duplicate IDs hoặc source ngoài checklist. `backend/tests/contract/test_architecture.py` giữ modules độc lập với HTTP/fixtures và giữ engines deterministic độc lập với DB/provider calls. Repositories được phép dùng kết nối DB chung.

Kiểm tra HTTP và persistence trên PostgreSQL test riêng:

```bash
TEST_DATABASE_URL='postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_test' \
  pytest -q -c backend/pyproject.toml backend/tests/e2e/test_api_storage.py
```

Quality evaluation theo BRD mục 13 có skeleton tại `evals/`; chưa có gold datasets/metric runners. Test software pass không thay thế đánh giá legal/model quality.
