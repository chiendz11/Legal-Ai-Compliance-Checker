# Backend theo module

Package `legal_checker` ở `backend/src/legal_checker/`. Kiến trúc hiện hành:
[system_architecture](../docs/architecture/system_architecture.md). Quyết định dữ liệu
và ownership năm người: [INTEGRATION_V1](../docs/contracts/integration_spec.md).

| Folder | Trách nhiệm và hiện trạng |
|---|---|
| api/v1 | 26 operations: upload, case/run/status/results, auth, review/report/export, health/knowledge |
| core | Config/PostgreSQL connection, logging/metrics, errors/security primitives |
| shared/contracts | C01–C13/X01/X02 và envelopes; live C09 provenance |
| shared/storage | Upload + cached HTTP(S), kiểm SHA và giới hạn nguồn |
| shared/llm | Types/config/client/audit; prompt và quyết định thuộc module |
| modules/documents | PDF text parser/chunker/profile/citations/writer; OCR/DOCX parser chưa có |
| modules/legal_knowledge | SQL reader và immutable snapshots |
| modules/applicable_law | Catalog scope/temporal; field/marker gaps giữ UNKNOWN |
| modules/citation_validation | Identity/temporal/domain/classifier; C09 pins |
| modules/retrieval | BM25 và tùy chọn hybrid/rerank; active chunk/fact metadata |
| modules/compliance | C07/C08, grounding/Decimal; verification provider do owner 4 cung cấp |
| modules/risks, recommendations | C10 hai nhánh và C11 templates, provenance/dedup |
| modules/assessments | Case/run lifecycle, Store standalone group C; không trộn hai loại run |
| modules/reviews, reports | Append-only review, immutable report versions, publish và export |
| workflows | Compose/run/validate DTO; completion và initial report cùng transaction |
| worker | Inline/Celery queue, Beat recovery, heartbeat/lease |
| migrations | Alembic revisions và SQL baselines |
| src/devtools | Dataset/QA/seed/update/read-only integration audit; không import vào business modules |

## Chạy từ root repo

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e './backend[dev,dataset]' -c constraints.txt
python -m uvicorn legal_checker.main:create_app --factory --host 127.0.0.1 --port 8000
```

[Dev setup](../docs/guides/dev_setup.md) và [DB local](../docs/database/local_setup.md)
có bước cấu hình `.env`, download và seed/update. Giữ DB/workbook/PDF/API keys ngoài Git.
modules dùng bytes thật, modules_di_reference chỉ DEV/EVAL; reference replay QA.
Live verifier/external source registry có port riêng, không default bật mọi gate.

## Kiểm tra

```bash
ruff check --config backend/pyproject.toml .
pytest -q -c backend/pyproject.toml
python -m devtools.integration_audit --output data/private/integration_audit
```

Tests DB cần TEST_DATABASE_URL có dbname legal_checker_test; tests tạo DB con riêng.
Schema/unit/handoff pass không chứng minh OCR/LLM/legal quality toàn corpus. Xem
[changelog](../docs/guides/integration_alignment_changes_20261105.md) cho bằng chứng và
các phần owner còn cần hoàn thiện/nghiệm thu. Thay schema dùng Alembic; thay dataset
là release dữ liệu riêng, không seed lại chỉ vì đổi code.
