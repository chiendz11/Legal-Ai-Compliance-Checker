# Checkpoint cuối nhóm C

**Giai đoạn 1, 2 và 3 hoàn thành trong phạm vi kỹ thuật đã yêu cầu.**
Thời điểm full verification: 29/10/2026 18:00, Asia/Saigon.
Repo: `C:\demo\Legal-Ai-Compliance-Checker`.

## Kết quả cuối

- Full pytest: **1259 passed**, **0 failed/errors**, **0 skipped**, một dependency warning.
- Ruff check toàn repo và Ruff format --check: **đạt**, **278 files** đúng format.
- Installed package/migration resources ngoài repo: **đạt**.
- PostgreSQL **18.4** test thật, loopback55433 và DB `legal_checker_test_*`; không ghi DB dev.
- Demo mới offline save/read/retry/replay, hai runs lịch sử, 37 lineage rows mỗi run
  chính; read và historical read không gọi engines. Không paid API calls.
- Instance PostgreSQL test đã dừng sạch, dữ liệu được giữ để đọc lại.

## Files sửa giai đoạn 3

- `backend/src/legal_checker/migrations/manager.py`, `schema_state.py`: canonical
  checksum CRLF và PG18 NOT NULL compatibility, vẫn chống schema/content tampering.
- `backend/src/legal_checker/shared/storage/http.py`: cache concurrency bounded
  retries, verified winner, xử lý Win32/CRT EACCES và persistent errors.
- `backend/src/devtools/dataset_download.py`: raw ZIP path/normalized alias checks.
- `backend/src/legal_checker/modules/assessments/run_group_c.py`: help ASCII cp1258.
- `docs/module_contracts.schema.json`: diagnostics cho ComplianceOutput/PipelineResult.
- `backend/tests/integration/test_alembic_migrations.py`, `test_source_storage_http.py`;
  `backend/tests/unit/test_migration_checksums.py` (mới), `test_dataset_download.py`,
  `test_workbook_seed.py`, `test_group_c_runner.py`: regressions cho lỗi thực tế.
- Imports/format tối thiểu để đạt Ruff: compliance mappers/run_c07, Knowledge/retrieval
  repositories, các unit/contract tests C07/LLM/numeric/review và hai audit scripts cũ.
- README gốc/backend/modules, architecture, module integration, hướng dẫn sau seed,
  thêm `docs/group_c_handoff.md`; cập nhật checklist nhóm C hiện có.
- Thư mục hoàn thành này chứa scripts/checks, demo/pins/lineage, báo cáo và manifests.

Working tree có sẵn edits giai đoạn trước và công việc chưa commit; đã giữ nguyên.
Không commit, reset, deploy, push hoặc thêm HTTP endpoint. Source ZIP bao gồm cả
tracked và untracked code hiện tại; patch chỉ chứa tracked changes. SQL migrations
lịch sử và baseline checksums không thay đổi.

## Lệnh kiểm chứng

```powershell
.\.venv\Scripts\python.exe -X utf8 outputs/group_c_completion_20261029_172537/verify_all.py --test-database-url postgresql://legal_checker@127.0.0.1:55433/legal_checker_test_completion
```

Exact subprocess commands/cwd/exit codes: `checks.json`. Full logs/JUnit giữ trong
folder này. Full run cuối **1259 passed in 276.75s**; trước sửa lần đầu có 7 failures,
sau đó còn một cache race. Đã tái hiện errno13/winerror=None, sửa có regression,
chạy 10 vòng race tests rồi chạy lại full suite đạt. Không thêm skip hoặc ignore lint.
Local Python3.14/PG18 khác version CI khai báo3.12/17.10; không claim remote CI đã chạy.

## Demo và handoff

Xem `HANDOFF.md`, `demo_verification.json`, `normalized_rows.json`,
`knowledge_snapshot.json`, `case_pins.json`, `saved_runs.json`, `demo_source.json`.
Tất cả source C02/C05/C06 có lineage; không lấy expected C07–C11 hoặc reference
observations làm đáp án. UNKNOWN có lý do thật, C09 NOT_RUN khi thiếu upstream.
`powershell.md` hướng dẫn read đúng run và chạy lại trong thư mục/DB test mới.

## Vấn đề còn lại / bước tiếp theo

Không còn blocker nhóm C được phát hiện qua các checks bắt buộc và demo đã chạy.
Tiếp theo là integration với upstream thật, human legal review/C12 và report/UI/C13
do nhóm khác sở hữu. Nhóm D đọc outputs đã lưu bằng exact case/run, giữ diagnostics,
exclusions và trạng thái nhánh; không chạy lại reasoning/risk/recommendation.
Review status và knowledge flags vẫn draft/unverified/PENDING.
