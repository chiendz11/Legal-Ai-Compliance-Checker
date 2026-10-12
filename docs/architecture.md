# Kiến trúc và skeleton theo BRD v1.1

Lựa chọn triển khai của nhánh này: **modular monolith Python/FastAPI**, giữ backend tại `app/` để không đổi lệnh chạy đã có. BRD mô tả yêu cầu nghiệp vụ, không bắt buộc dùng microservices hoặc chọn framework frontend.

## Cấu trúc

```text
app/
├── main.py                    # Composition root / factory
├── bootstrap.py               # Nối port với adapter thật
├── api/
│   ├── dependencies.py
│   └── v1/
│       ├── router.py
│       └── routes/            # HTTP, validation input, status/error mapping
├── contracts/                 # Pydantic theo ownership C01–C13, X01/X02
├── core/                      # Settings, stable IDs, conflict errors, shared validation
├── application/
│   ├── ports/                 # Knowledge, run store, authorization, LLM audit
│   ├── validation.py          # Kiểm tra contracts ở ranh giới downstream
│   └── pipelines/
│       ├── assessment.py      # Interface full flow, chưa chạy bước 1–9
│       ├── draft_assessment.py # Wiring bước 1–7 với upstream adapters được inject
│       └── steps_5_7.py        # Pipeline đang hoạt động
├── modules/
│   ├── intake/                # Bước 1
│   ├── document_intelligence/ # Bước 2: profile/chunks/citations
│   ├── scope_resolver/        # Bước 3A: scope/checklist
│   ├── temporal_resolver/     # Bước 3A: version/relevant date
│   ├── citation_validation/   # Bước 3B: nhánh độc lập
│   ├── retrieval/             # Bước 4
│   ├── compliance_reasoning/  # Bước 5: evidence gates, finding, numeric rules
│   ├── rule_aggregation/      # Bước 5: C07 → C08
│   ├── risk/                  # Bước 6
│   ├── recommendation/        # Bước 7
│   ├── human_review/          # Bước 8
│   ├── reporting/             # Bước 9
│   └── knowledge_curation/    # Nguồn luật, approval, release snapshot
└── infrastructure/
    ├── authorization/         # Identity/case/reviewer/curator adapters tương lai
    ├── observability/         # Trace/audit adapters tương lai, X02 cho LLM thật
    ├── reporting/             # Report storage/export adapters tương lai
    ├── knowledge/             # JSON snapshot adapter hiện có
    ├── persistence/           # SQLite adapter hiện có
    ├── llm/                   # Provider adapters tương lai
    ├── documents/             # Storage/PDF/DOCX/OCR adapters tương lai
    └── retrieval/             # FTS/vector/reranker adapters tương lai
frontend/src/                  # Folder skeleton, chưa chọn framework/UI runtime
├── features/                  # upload, assessments, review, reports, knowledge
└── shared/                    # api, components
scripts/                       # Import workbook, export OpenAPI, E2E HTTP
tests/                         # Regression, contract boundaries, workflow integration
data/                          # Knowledge public và data/private bị gitignore
docs/                          # BRD, contracts, OpenAPI, architecture và hướng dẫn
configs/                       # Configuration ownership, chưa có cấu hình provider mới
evals/gold/                    # Skeleton đánh giá chất lượng theo BRD mục 13
```

## Mapping BRD → module → contracts → trạng thái

| Module | BRD | Input → Output | Trạng thái nhánh này |
|---|---|---|---|
| Intake | BR-01 | Source/context → C01 | Interface + schema |
| Document Intelligence | BR-02, BR-19 | C01 → C02 + C03 + chunks | Interface + schema |
| Scope Resolver | BR-03, BR-04, BR-06 | C02 + knowledge → C04 | Interface + schema |
| Temporal Resolver | BR-05 | C04 + C02 + knowledge → C05 | Interface; C05 hiện dùng ở bước 5 |
| Citation Validator | BR-20–24 | C03 + profile/legal sources → C09 | Interface; C09 hiện dùng ở risk |
| Retrieval | BR-07, BR-08 | C05 + criterion/chunks → C06 | Interface; C06 hiện dùng ở reasoning |
| Compliance Reasoning | BR-08, BR-09, BR-13, BR-16 | C05 + C06 + knowledge/chunks/observations → C07 | Đã chạy; numeric rule + gates; chưa nối LLM |
| Rule Aggregator | BR-10 | C05 + C07 + aggregation rule → C08 | Đã chạy |
| Risk | BR-11, BR-25 | C07 + C09 + risk rules/catalog → C10 | Đã chạy |
| Recommendation | BR-12 | C10 + requirement/context + template/link → C11 | Đã chạy bằng template |
| Human Review | BR-14, BR-18, AC-06 | AI output + reviewer → C12 | Interface + schema |
| Report | BR-15, AC-11 | C02/C05/C07–C12 + snapshot → C13 | Interface + schema |
| Knowledge Curation | BQ-08, BO-02 | Curator-approved knowledge → X01 | Interface; JSON import/checksum đã có |

Skeleton C01–C04/C12/C13/X01/X02 là starter schemas/interface để team có thể mở rộng; chúng chưa chứng minh acceptance criteria tương ứng đã hoàn thành. Profile/report có các JSON object cần hoàn thiện theo bảng runtime khi xây module. Các interface `Protocol` không có giả lập kết quả hoặc route trả thành công cho chức năng chưa có.

## Ranh giới dependency

- API đọc contracts, gọi application/module services và chuyển lỗi sang HTTP.
- Pipeline điều phối, truyền Context và input cần thiết cho mỗi module.
- Business modules đọc contracts + core + port interfaces; không import FastAPI, SQLite hoặc provider cụ thể.
- Infrastructure hiện thực ports; `bootstrap.py` nối implementations. `create_app(services=...)` cho phép thay adapter khi integration test.
- Contracts không chứa lời gọi HTTP/DB/LLM. Module không sửa field thuộc owner khác.
- Full-assessment skeleton giữ Applicable Law và Citation Validation độc lập đến Risk/Report. Scope không nhận contract citations làm input.

C05 là context áp dụng cho case, được Temporal Resolver tạo và cả Retrieval/Reasoning sử dụng. C06 là evidence references; không thay thế checklist hoặc quyết định scope/version. Endpoint `/api/v1/reasoning` nhận `CriterionReasoningInput` chỉ chứa C05/C06/chunks/observations. `Steps57Input` chỉ thuộc endpoint pipeline; citation branch hội tụ tại risk.

C07 tổng hợp evidence cho một criterion; C08 nhóm findings C07 theo `yeu_cau_ca_id` và dùng aggregation rule. Risk đọc C07/C09; citation không sửa C08. Recommendation giữ severity và pending review.

## Chỗ nối LLM và audit

`modules/compliance_reasoning/ports.py` định nghĩa `CriterionProposalProvider`: nhận context/requirement/criterion/evidence/knowledge, trả finding/giải thích/quotes. Output proposal không có trusted gates. Provider implementation sẽ đặt trong `infrastructure/llm/`; orchestration/adapter phải ghép proposal với facts/gates đã xác minh rồi đưa vào engine.

Port này chưa được gọi trong runtime hiện tại. Không có API key/provider mặc định hoặc log LLM giả. Khi tích hợp thật phải dùng X02 (`contracts/audit.py`) và `LlmAuditSink`. Recommendation LLM tương lai phải bảo toàn evidence/legal basis/action/severity và template constraints.

Authorization (`AccessPolicy`) là interface cho phân quyền case/tenant/reviewer/curator. Nó chưa được cắm vào API hiện tại; chưa có production auth hoặc full reviewed-result/report publishing.

## Tương thích và kiểm tra

Pipeline dùng `app.application.pipelines.steps_5_7`, engines dùng `app.modules.*`, validation dùng `app.core.validation`/`app.application.validation`; contracts import theo owning module. Các file/package chuyển tiếp của cấu trúc trước đã được xóa. Factory nhận `Settings` hoặc adapters được inject qua `Services`; cấu hình mặc định đọc environment. Knowledge snapshot và SQLite schema giữ nguyên. Xem [hướng dẫn integration](module_integration.md) và [infrastructure adapters](../app/infrastructure/README.md).

Nhánh `feat/brd-system-skeleton-v2` bổ sung `contracts/workflow.py` và `DraftAssessmentWorkflow`. Workflow giữ C01 pin, kiểm tra profile/chunks/citations cùng hợp đồng, bảo toàn checklist và field scope khi Temporal tạo C05, rồi chuyển input đã ghép vào pipeline bước 5–7. `ObservationProvider` nối facts/gates đã xác minh với đề xuất rule/LLM. Workflow không tự tạo adapter mặc định và không trả báo cáo published. Upstream production quality chưa được chứng minh bằng test fixtures.

Ports mới: `source_documents.py`, `evidence_search.py`, `review_store.py`, `report_store.py`. Infrastructure có chỗ đặt authorization, observability và reporting adapters. Frontend assessments được chia tiếp thành profile/checklist/evidence/compliance/citations/risks/recommendations. Xem [module integration](module_integration.md).

Validation C05/C09 được tách thành helper riêng; API downstream không tạo một input pipeline giả để kiểm tra context. C07 consumer kiểm tra legal basis và decision-rule snapshot; C10 consumer kiểm tra risk rule, branch, criterion checklist, severity và legal basis trước khi chọn khuyến nghị. Duplicate requirement/citation/risk IDs bị từ chối.

```bash
ruff check .
ruff format --check .
pytest -q
python scripts/export_openapi.py
```

Để chạy E2E HTTP, bật server như README rồi chạy:

```bash
python scripts/e2e_steps_5_7.py
```

Script gọi reasoning → aggregation → risk → recommendation; so sánh với pipeline, GET snapshot và kiểm tra idempotency. Mỗi lần có run ID mới; output mặc định ở `data/private/e2e_result.json`.
