# Checklist hoàn thành nhóm C

Ngày 29/10/2026, Asia/Saigon. Tiếp tục từ checkpoints giai đoạn 1–2.
**Nghiệm thu giai đoạn 3: ĐẠT — 29/10/2026 18:00, Asia/Saigon.**
Không sử dụng C07/C08/C10/C11 EXPECTED hoặc observations tham chiếu làm đáp án;
không gọi API trả phí. Không ghi DB dev.

| Tiêu chí | Implementation / evidence | Trạng thái |
|---|---|---|
| C07/C08/C10/C11 và tests nghiệp vụ | Full regression 1259 tests; bốn findings, provenance/gates, policy, templates | Đạt |
| Workflow, runner, PostgreSQL, demo save/read | Demo mới hai runs; DTO/hash/normalized/lineage; read không recompute | Đạt |
| Runtime models và JSON schemas | Hai diagnostics fields; machine contracts 23 tests | Đạt |
| SQL checksum LF/CRLF, không sửa migration/baseline | 9 checksum unit + 19 migration integration tests; PG18 NOT NULL vẫn kiểm tra | Đạt |
| Cache concurrency và ZIP raw paths Windows | 31 storage + 17 ZIP/dataset tests; 10 vòng concurrency/regression liên tiếp | Đạt |
| Ruff check/format toàn repo | All checks passed; 278 files already formatted; không blanket-ignore | Đạt |
| Full pytest với PostgreSQL test thật | 1259 passed, 0 failed/errors, 0 skipped; PG18.4 test riêng | Đạt |
| README/modules/architecture/hướng dẫn khớp implementation | 8 docs đồng bộ + docs/group_c_handoff.md; ranh giới C13 rõ | Đạt |
| Gói bàn giao có input/output/diagnostics/hash/lineage/checks | HANDOFF/checkpoint, source ZIP, manifests; assemble.py kiểm tra CRC/SHA | Đạt; xác nhận bằng package_metadata.json và manifests |

Kết quả cuối có trong `checks.json`, `pytest.xml` và logs. Demo có trong
`demo_verification.json`, `normalized_rows.json`, `case_pins.json`, `saved_runs.json`
và `knowledge_snapshot.json`; trạng thái đóng gói trong `package_metadata.json`.
Các checkpoints giai đoạn 1–2 giữ nguyên bằng chứng lịch sử.

Không còn blocker kỹ thuật nhóm C được phát hiện trong phạm vi nghiệm thu này.
Upstream thật, human legal review/C12, UI và C13 publish/export vẫn thuộc nhóm khác.
Demo giữ draft/PENDING và UNKNOWN có lý do; không coi snapshot là phê duyệt pháp lý.
