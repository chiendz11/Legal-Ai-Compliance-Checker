# Verification ownership

Existing test paths remain stable for scripts/users integrating the first branch.

- `test_pipeline.py`, `test_numeric.py`, `test_citation.py`: business gates, uncertainty, aggregation, numeric boundary checks and branch independence.
- `test_knowledge.py`: imported knowledge relationships.
- `test_modules.py`, `test_api_storage.py`: predecessor contracts, HTTP integration, transactional snapshots, conflicts and idempotency.
- `test_skeleton_integration.py`: canonical reasoning input/legacy compatibility, dependency injection and environment configuration.
- `scripts/e2e_steps_5_7.py`: live HTTP E2E for implemented steps 5–7.

Add module unit/contract tests as skeleton implementations become available. Full BRD steps 1–9 E2E and quality metrics (retrieval recall, temporal accuracy, grounding, human review and report authorization) remain future work.
