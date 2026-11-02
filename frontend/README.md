# Frontend — BRD step 9 and reviewer/curator screens

Vite + React 18 + TypeScript. Data fetching uses TanStack Query and an `openapi-fetch` client typed from `docs/architecture/openapi.design.json`. In dev, `/api` and `/health` go through the Vite proxy to the backend. MSW can serve cases/reports from local fixtures instead, for UI work without a backend.

## Run

Needs Node 20+ and the backend on 127.0.0.1:8000 (see [docs/guides/demo.md](../docs/guides/demo.md)). From `frontend/`:

```bash
npm install
npm run dev                     # http://localhost:5173
```

Offline mode: copy `.env.example` to `.env.local`, set `VITE_API_MOCK=true`, and export fixtures from your seeded DB (they are Git-ignored), from the repo root:

```bash
python -m scripts.ui_fixtures                   # 5 diverse DEV cases
python -m scripts.ui_fixtures --case CA360_051  # specific cases
```

Fixtures are QA `EXPECTED` C13 references for layout only, and the UI labels them as mock data. Mock mode serves case/report reads only (as a view-only user); starting runs, review and export need the backend. Production builds never include MSW or fixtures. `Dockerfile` + `nginx.conf` serve the build and proxy `/api` to the `api` service (see `compose.yaml`).

| Command | Purpose |
|---|---|
| `npm run dev` | Dev server with backend proxy (or mock) |
| `npm run build` | Typecheck and production build |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run gen:api` | Regenerate `src/shared/api/schema.d.ts` after `docs/architecture/openapi.design.json` changes |

## Layout

- `src/shared/api`: generated `schema.d.ts`, typed client and React Query hooks. UI never talks to the DB or an LLM.
- `src/mocks`: MSW handlers and `mocks/fixtures/` for offline mode.
- `src/features/auth`: login page shown when `/api/v1/auth/me` answers 401 (`AUTH_MODE=on`). The session is an HttpOnly cookie; the page never stores tokens. `src/shared/auth.ts` hides actions a role cannot do; the server still enforces every role.
- `src/features/upload`: C01 intake (PDF/DOCX upload, case creation, optional run).
- `src/features/cases`: history with server-side filters/sort/paging in the URL, "Chạy đánh giá" (POST run with a fresh `Idempotency-Key`), run progress per stage over SSE (polling fallback), then the run's newest report.
- `src/features/reports`: report page, summary tiles, tabs, audit with C12 history, split view beside the original PDF, PDF/DOCX/JSON export links, and ID lookups used to link risk → finding → evidence. Tab and focused finding live in the URL (`?tab=risks&focus=<id>`).
- `src/features/review`: reviewer workbench ("Rà soát" tab): decisions with reason and expected hash, rebuild a reviewed report version, publish.
- `src/features/assessments/*`: one section per contract — profile (C02), checklist (C04/C05), compliance (C07/C08), citations (C03/C09), risks (C10), recommendations (C11).
- `src/features/knowledge`: not built yet (X01 curation).
- `src/shared/components`: status badges, evidence quotes, tables and other shared display pieces.

Do not recalculate C08/C10 statuses in the UI, derive applicable law from contract citations, or present pending AI output as a published/reviewed report. Unknown/null values and UNKNOWN/INSUFFICIENT stay visible; the summary shows counts, not a compliance score. Reports from `REFERENCE_REPLAY` runs are labelled as such.
