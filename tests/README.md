# Verification ownership

Existing test paths remain stable for scripts/users integrating the first branch.

- `test_pipeline.py`, `test_numeric.py`, `test_citation.py`: business gates, uncertainty, aggregation, numeric boundary checks and branch independence.
- `test_knowledge.py`: imported knowledge relationships.
- `test_modules.py`, `test_api_storage.py`: predecessor contracts, HTTP integration, transactional snapshots, conflicts and idempotency.
- `test_skeleton_integration.py`: reasoning contract ownership, rejection of pipeline payloads, dependency injection and Settings/environment configuration.
- `test_draft_workflow.py`: injected synthetic upstream adapters, case pins, scope ownership and citation/compliance independence.
- `test_downstream_boundaries.py`: reject tampered C07/C10 snapshots/provenance, duplicates and foreign risk sources.
- `test_architecture.py`: business modules cannot import HTTP or concrete infrastructure adapters.
- `scripts/e2e_steps_5_7.py`: live HTTP E2E for implemented steps 5–7.
- `parallel/test_person_1_documents.py` through `test_person_5_integration.py`: independent conformance checks using shared handoffs, plus real downstream engines/draft integration over fixture upstream services.
- `parallel/test_fixture_tools.py`: reproducible source/checkpoints, pinned checksums and CLI validation of an output file from an external implementation.

Per-person commands, ownership and fixture limitations are documented in [parallel development](../docs/parallel_development.md).

Add module unit/contract tests as skeleton implementations become available. Full BRD steps 1–9 E2E and quality metrics (retrieval recall, temporal accuracy, grounding, human review and report authorization) remain future work.
