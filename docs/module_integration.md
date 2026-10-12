# Nối các module theo BRD v1.1

## Cấu trúc và điểm nối

Giữ backend tại `app/`; `api/` xử lý HTTP, `contracts/` giữ Pydantic schemas, `business_modules/` giữ nghiệp vụ, `workflows/` điều phối, `adapters/` hiện thực storage/provider adapters. Frontend skeleton dùng feature folders, chưa chọn framework.

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

`app/workflows/pipelines/draft_assessment.py` cung cấp wiring executable khi tất cả upstream adapters được inject:

```python
from app.workflows.pipelines.draft_assessment import DraftAssessmentWorkflow, DraftModules

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

- `shared/validation.py` kiểm tra context snapshot, C05 và C09 độc lập. Request reasoning/pipeline tái sử dụng các helpers.
- `workflows/validation.py` kiểm tra C07/C10 tại consumer boundaries. C07 legal basis/decision rule phải khớp knowledge snapshot. C10 rule/catalog/branch/criterion/version/severity/legal basis phải khớp; không cho downstream tự nâng severity hoặc đổi nguồn risk.
- HTTP routes gọi validation/module services; không chứa rule pháp lý. Imports dùng module sở hữu. Reasoning nhận `CriterionReasoningInput`; pipeline nhận `Steps57Input` riêng.
- `contracts/workflow.py` là checkpoint draft nội bộ để ghép module, không tạo thêm bảng DB cho logical contract.

## Adapter và ownership

Imports theo module sở hữu:

| Chức năng | Module canonical |
|---|---|
| Pipeline `evaluate` | `app.workflows.pipelines.steps_5_7` |
| Reasoning `reason` | `app.business_modules.compliance_reasoning.service` |
| Numeric rules `numeric_finding` | `app.business_modules.compliance_reasoning.numeric_rules` |
| Aggregation `aggregate` | `app.business_modules.rule_aggregation.service` |
| Risk engines | `app.business_modules.risk.service` |
| Recommendation `recommend` | `app.business_modules.recommendation.service` |
| Downstream validation | `app.workflows.validation` |
| Request/context validation | `app.shared.validation` |
| Stable IDs | `app.shared.ids` |

Khi gọi engines trực tiếp, truyền `Context` cùng requirements/citations theo chữ ký hiện tại; pipeline trong workflows chịu trách nhiệm ghép các inputs này. Contracts được import từ `contracts/reasoning.py`, `contracts/pipeline.py`, `contracts/risk.py` và các owning modules khác. Knowledge adapter ở `adapters/knowledge_sources/snapshot.py`; run store ở `adapters/database/sqlite.py`.

```python
from app.workflows.pipelines.steps_5_7 import evaluate
from app.business_modules.rule_aggregation.service import aggregate

response = evaluate(pipeline_request, knowledge)
results = aggregate(context, knowledge, criterion_results, applicable_requirements)
```

Factory dùng một cấu hình `Settings` rõ ràng hoặc đọc environment khi không truyền settings:

```python
from pathlib import Path

from app.shared.config import Settings
from app.main import create_app

api = create_app(
    settings=Settings(
        knowledge_path=Path("data/knowledge.json"),
        database_path=Path("data/private/runtime.sqlite3"),
    )
)
```

`bootstrap.py` là composition root tạo và nối adapters với ports, không phải import alias. `main.py` tạo FastAPI và router. Trong tests có thể inject `Services` bằng `create_app(settings=settings, services=services)` để thay storage mà không tạo DB mặc định.

Các clients gọi riêng Reasoning gửi `contract_name=CriterionReasoningInput` và payload C05/C06/chunks/observations, theo `examples/reasoning.json`. C09/citations được gửi tới Risk hoặc pipeline; Reasoning từ chối payload pipeline với HTTP 422. Script E2E xây từng request đúng contract và đối chiếu output với pipeline.

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
