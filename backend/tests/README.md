# Tests

- `unit/`: dataset download/checksum, Excel conversions và QA validation.
- `contract/`: schema/provenance, independent branch boundaries, OpenAPI/JSON Schema validity và đối chiếu đặc tả với models; không sinh/ghi file JSON.
- `integration/`: Alembic (DB mới, tiếp nhận DB cũ, phát hiện schema lệch, rollback và chạy đồng thời), PostgreSQL seed/snapshots, installed package, workflow wiring và HTTP source/cache.
- `e2e/`: các route module nội bộ không công khai/không ghi DB; GET đọc run đã lưu.

Set `TEST_DATABASE_URL` to a PostgreSQL role with CREATEDB and a database name prefixed
`legal_checker_test`. Tests create/drop uniquely named test databases; never write the dev DB.
CI always enables the PostgreSQL service. Without the variable, DB-dependent tests skip.

`seed_knowledge.sql` is a compact regression baseline retained from previously public
knowledge examples. It is not approved legal gold and contains no private contract corpus.
Module handoffs are constructed/validated in tests and loaded from PostgreSQL where needed;
there is no checked-in JSON/DOCX scenario pack or replay runner.

```bash
TEST_DATABASE_URL='postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_test' \
  pytest -q -c backend/pyproject.toml
```

Real PDF/OCR/search/LLM quality still requires actual implementations and independently
annotated sources/expected outputs. Refer to the module development guide in `docs/`.

Công cụ dựng dataset cũ và tests của chúng đã xóa. `seed_helpers.py` chỉ tạo rows/payload/workbook nhỏ cho tests reader/seed; không tạo dataset hoặc đáp án pháp lý. Tests nghiệp vụ các module cần được bổ sung khi nhóm triển khai.
