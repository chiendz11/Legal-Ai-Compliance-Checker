# Frontend skeleton — BRD step 9 and reviewer/curator screens

This directory defines ownership and feature boundaries. No frontend framework, build tooling or runnable UI has been selected yet.

- `src/features/upload`: PDF/DOCX intake, source metadata, case creation (C01).
- `src/features/assessments`: profile, checklist, evidence, compliance, citations, risks and recommendations (C02, C05–C11).
- `src/features/review`: permission-aware confirm/override/request-evidence with append-only C12 events.
- `src/features/reports`: render separate compliance/citation risk sections and export C13.
- `src/features/knowledge`: legal source/version/criterion/risk catalog curation and release snapshots (X01).
- `src/shared/api`: generated clients/types from `docs/openapi.json` once a stack is selected.
- `src/shared/components`: evidence viewer, status badges and reusable display components.

Do not recalculate C08/C10 statuses in the UI, derive applicable law from contract citations, or present pending AI output as a published/reviewed report.
