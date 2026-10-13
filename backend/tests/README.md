# Tests

- `unit/`: gate, numeric/aggregation/risk logic, Excel conversions.
- `contract/`: schema/provenance and independent branch boundaries.
- `integration/`: PostgreSQL seed/snapshots, installed package and workflow wiring.
- `e2e/`: HTTP endpoints, normalized SQL persistence, idempotency/conflicts.

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
