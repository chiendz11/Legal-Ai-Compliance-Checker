# Bắt đầu phát triển song song theo phân công 5 người

Nhánh `feat/parallel-module-starter` cung cấp contracts, input/output mẫu và conformance tests để mỗi người bắt đầu trước khi modules phía trước hoàn thành. Knowledge dùng snapshot hiện tại; mọi input của cùng case giữ nguyên IDs, deployment, run, trace và checksum.

## Chạy lần đầu

Từ thư mục repo, với Python 3.11+:

```bash
source .venv/bin/activate
pip install -e '.[dev]' -c constraints.txt
python -m scripts.parallel_dev --all-scenarios
pytest -q tests/parallel
```

Nếu chưa có `.venv`, tạo bằng `python -m venv .venv` trước khi activate. Lệnh install cập nhật editable package để import được `devtools` mới. Demo không cần DB, API key, queue hay services upstream đang chạy.

`parallel_dev` in 35 kết quả: 5 vai trò × 7 scenarios. Người 1–3 chạy `fixture_replay`, Người 4 chạy engines hiện có với structured observations mẫu, Người 5 chạy draft workflow bằng upstream fixtures rồi dựng report. Đây là kiểm tra contracts/wiring, chưa đo độ chính xác OCR, retrieval hay LLM.

## Ownership và điểm bàn giao

| Người | Code sở hữu hiện tại | Input files | Output model/file |
|---|---|---|---|
| 1: Data/Document | `business_modules/document_intelligence`, `knowledge_curation`; adapters tài liệu/knowledge | `document_input.json`, `source.docx` | `DocumentIntelligenceResult` / `document_output.json`: C02, chunks, C03 |
| 2: Legal | `scope_resolver`, `temporal_resolver`, `citation_validation` | `scope_input.json`, `temporal_input.json`, `citation_input.json` | `LegalOutput` / `legal_output.json`: C04, C05, C09 |
| 3: Retrieval | `business_modules/retrieval`, `adapters/search_backends` | `retrieval_input.json`: C05 + chunks | `list[RetrievalEvidence]` / `retrieval_output.json`: C06 |
| 4: Compliance | `compliance_reasoning`, `rule_aggregation`, compliance risk/recommendation | `compliance_input.json`: C05 + C06 + chunks + observations | `ComplianceOutput` / `compliance_output.json`: C07, C08 và criterion-sourced risks/actions |
| 5: Integration/UI | `api`, `workflows`, persistence, draft report, frontend | `integration_input.json`: document + legal + compliance | `FinalReport` / `report_output.json`: C13 draft; `pipeline_output.json` là checkpoint C07–C11 |

Người 5 nối modules và hợp nhất nhánh citation. Người 4 không tạo citation warnings; `ComplianceOutput` từ chối risks có nguồn citation. Interface của từng module vẫn nằm tại owning service/ports hiện tại.

Contracts nằm trong `app/contracts/handoffs.py` và tái sử dụng schemas C01–C11/C13. Schema JSON cho tooling/frontend: `docs/parallel_contracts.schema.json`. DTOs bàn giao này chưa được mở thành các HTTP endpoints mới.

## Scenarios có sẵn

Các files nằm tại `examples/parallel/<scenario>/`:

| Scenario | C07 | C08 | Risk kỳ vọng |
|---|---|---|---|
| `satisfied` | 3 SATISFIED | COMPLIANT | Không có |
| `violated` | 1 VIOLATED + 2 SATISFIED | NON_COMPLIANT | 1 compliance |
| `missing` | 3 MISSING | NON_COMPLIANT | 3 compliance |
| `partial` | 1 SATISFIED + 2 MISSING | PARTIAL | 2 compliance |
| `insufficient_evidence` | 3 UNKNOWN, C06 rỗng | INSUFFICIENT | 3 verification |
| `unknown_version` | C07 rỗng vì chưa chọn được version | INSUFFICIENT | Không tự tạo substantive risk |
| `stale_citation` | 3 SATISFIED | COMPLIANT | 1 citation; compliance không đổi |

Manifest ghi `fixture_only=true` và `SYNTHETIC_NOT_GOLD_NOT_HUMAN_VERIFIED`. DOCX là tài liệu tổng hợp thực, đọc được bằng parser; proposed findings/gates trong fixtures là giả định kiểm tra wiring, không phải nhãn gold hoặc kết luận được kiểm chứng từ nội dung DOCX. Cờ verification trong citation snapshot chỉ mô phỏng nhánh rule, không xác nhận nguồn pháp lý thật. Knowledge gốc và trạng thái chưa human-approved của nó được giữ nguyên.

Manifest pin checksum knowledge, checksum mọi JSON và source DOCX. Loader kiểm tra schema, nguồn, provenance và liên kết giữa các checkpoint. Fixtures khác scenario có case/run/trace IDs khác nhau; không trộn các files giữa scenarios.

Snapshot hiện chứa 12 bảng phục vụ engines bước 5–7 và các nguồn/version pháp lý liên quan. Bộ dữ liệu scope/checklist, annotations và gold evaluation đầy đủ vẫn cần Người 1/2 bổ sung; fixtures hiện cho phép bắt đầu interfaces, rules và tests trước khi có release dữ liệu đó.

## Chạy và lấy input/output theo người

Ví dụ Người 3:

```bash
python -m scripts.parallel_dev --person 3 --scenario satisfied \
  --output-dir data/private/parallel
pytest -q tests/parallel/test_person_3_retrieval.py
```

Input được ghi tại `data/private/parallel/satisfied/person_3/input.json`; output tham chiếu ở cùng folder. Chạy tương tự bằng `--person 1`, `2`, `4`, `5`. Thư mục output nằm trong `data/private` đã gitignore.

Tests riêng:

```bash
pytest -q tests/parallel/test_person_1_documents.py
pytest -q tests/parallel/test_person_2_legal.py
pytest -q tests/parallel/test_person_3_retrieval.py
pytest -q tests/parallel/test_person_4_compliance.py
pytest -q tests/parallel/test_person_5_integration.py
```

Mỗi người load input bằng các Pydantic models trong `handoffs.py`, gọi code riêng rồi serialize output bằng `model_dump(mode="json")` hoặc `model_dump_json()`. Với output list, serialize từng phần tử. Người 2 trả object có ba keys `scope`, `requirements`, `citations`; branch scope nhận `ScopeInput` không có field citations.

## Kiểm tra output của implementation thật

Ví dụ Người 3 đã ghi kết quả vào `data/private/my_retrieval_output.json`:

```bash
python -m scripts.parallel_dev --person 3 --scenario satisfied \
  --verify-output data/private/my_retrieval_output.json
```

Lệnh trả exit code 0 nếu output đáp ứng schema và các checks tại điểm bàn giao; sai schema, foreign IDs, checksum, run hoặc provenance trả exit code 1. `--verify-output` dành cho một người và một scenario.

Có thể thêm `--compare-reference` để yêu cầu output giống reference JSON tổng hợp. Conformance pass không chứng minh model dự đoán đúng về mặt pháp lý. Với Người 4, validator còn kiểm tra C08/risk/recommendation theo rules/templates hiện tại; những ràng buộc này là baseline của `parallel-v1`, cần cập nhật contracts/tests khi mở rộng recommendation bằng LLM.

Các validator gọi trực tiếp được từ tests tại `app/workflows/handoffs.py`: `validate_document`, `validate_legal`, `validate_retrieval`, `validate_compliance`, `validate_report`.

## Thay riêng một module mẫu trong workflow chung

`devtools/replay.py` tạo upstream fixtures với đúng interfaces hiện có. `dataclasses.replace` thay một slot bằng implementation của bạn. Đây là integration test template cho một RetrievalService đã được bạn khởi tạo:

```python
from dataclasses import replace

from app.adapters.knowledge_sources.snapshot import Knowledge
from app.workflows.pipelines.draft_assessment import DraftAssessmentWorkflow
from devtools.parallel import FIXTURE_ROOT, FixturePack
from devtools.replay import fixture_modules


def check_my_retrieval(my_retrieval_service):
    knowledge = Knowledge()
    pack = FixturePack.load(FIXTURE_ROOT / "satisfied", knowledge)
    modules = replace(
        fixture_modules(pack.handoffs),
        retrieval=my_retrieval_service,
    )
    draft = DraftAssessmentWorkflow(modules, knowledge).evaluate(
        pack.handoffs.document_input.case,
        pack.handoffs.document_input.context,
    )
    return draft
```

Các slots khác: `documents`, `scope`, `temporal`, `citations`, `observations`, `intake`. Người 4 nối provider với facts/gates đã xác minh qua `observations`; engine nhận structured observations và kiểm tra guards. Khi thay implementation thật, findings có thể khác reference và cần benchmark bằng dữ liệu gold riêng.

Người 1 dùng `pack.read_source(case.source)` để lấy bytes DOCX trong test; hàm kiểm tra source/hash và chỉ đọc nguồn fixture đã pin. Source URI `fixture://...` không phải URL object storage production.

`AssessmentDraft` giữ cả `extracted_citations` và `citation_findings`. `report_input_from_draft()` chuyển draft thành input cho report, bảo toàn C09 và tách criterion-sourced risks của Người 4. `business_modules/reporting/draft.py` chỉ dựng C13 `DRAFT/PENDING`, chưa export/persist/publish report.

## Quy tắc sửa phần chung

- Chủ module đề xuất thay đổi schema qua PR và cập nhật producer/consumer, schema JSON, fixtures và tests cùng lúc. Người 5 giữ phần nối; Người 1 giữ phiên bản knowledge.
- C07 dùng SATISFIED/MISSING/VIOLATED/UNKNOWN; C08 dùng COMPLIANT/PARTIAL/NON_COMPLIANT/INSUFFICIENT.
- `profile` C02 có fields typed/nullable. Giá trị đã biết cần fact `ten_truong=profile.<field>` và evidence truy được về chunk; unknown giữ null. Boolean UNKNOWN không được ép thành false.
- Quote offsets dùng chỉ số ký tự Python/Unicode. Chunk/evidence không tự strip whitespace.
- Temporal giữ checklist, nhóm phiên bản và scope provenance của C04. C09 cần bao phủ citations đã trích xuất; unresolved citation có thể trả UNKNOWN.
- Checklist rỗng chưa được hỗ trợ trong baseline. Scope/version chưa rõ giữ UNKNOWN/INSUFFICIENT; kết quả AI và report vẫn chờ review.

Khi đổi snapshot hoặc schemas, regenerate từ root repo và review diff:

```bash
python -m scripts.generate_parallel_fixtures
python -m scripts.export_parallel_contracts
python -m scripts.export_openapi
python -m scripts.parallel_dev --all-scenarios
pytest -q
```

Gói này không triển khai PostgreSQL, queue, OCR/LLM/search providers hay production authentication. Những phần đó có thể phát triển song song và thay vào các điểm bàn giao đã có. CI hiện chạy toàn bộ tests, bao gồm `tests/parallel`.
