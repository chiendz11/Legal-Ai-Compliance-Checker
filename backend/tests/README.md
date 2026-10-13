# Verification ownership

- `unit/`: reasoning, numeric boundaries, aggregation, citation risk rules and knowledge relationships.
- `integration/`: injected draft workflow, service composition, environment configuration and installed package startup outside the repository.
- `contract/`: downstream C07/C10 provenance checks, module dependency boundaries and `parallel/` handoff conformance tests for five roles.
- `e2e/test_api_storage.py`: HTTP steps-5-7 pipeline through real engines and SQLite, snapshot GET, conflicts and idempotency. This uses synthetic input; it is not PDF/OCR-to-report E2E.
- Root `scripts/e2e_steps_5_7.py`: live HTTP reasoning → aggregation → risks → recommendations, comparison with pipeline and stored output.

From the repository root:

```bash
pytest -q -c backend/pyproject.toml
pytest -q -c backend/pyproject.toml backend/tests/contract/parallel
```

From `backend/`, use `pytest -q` after installing the package.

[Parallel development](../../docs/parallel_development.md) describes per-person commands, ownership and fixture limitations. Complete PDF extraction, retrieval/LLM quality, review and publishing tests require real implementations and independently checked expected outputs.
