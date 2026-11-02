# Checklist nhóm C — triển khai theo giai đoạn

**Cập nhật 29/10/2026 18:00:** giai đoạn 3 đã đạt **1259 passed, 0 failed,
0 skipped** trên full suite với PostgreSQL test thật. Ruff toàn repo và installed
package/resource checks đạt. Schemas/tài liệu đã đồng bộ; các lỗi checksum SQL,
PG18 fingerprint, cache concurrency và ZIP raw paths đã có regression tests.
Xem [checklist hoàn thành](../group_c_completion_20261029_172537/checklist.md) và
[báo cáo bàn giao](../group_c_completion_20261029_172537/HANDOFF.md).
Các cập nhật giai đoạn 1–2 dưới đây là mốc lịch sử.

**Cập nhật 29/10/2026:** giai đoạn 2 đã đạt workflow/runner/persistence và demo
offline save/read/retry/replay. Kiểm chứng cuối **1009 passed, 0 failed, 0 skipped**;
PostgreSQL 18.4 test thật; Ruff check/format trên 14 files đạt. Xem
[checklist giai đoạn 2](../group_c_phase2_20261029_010014/checklist.md) và
[checkpoint giai đoạn 2](../group_c_phase2_20261029_010014/checkpoint.md).
Giai đoạn 3 chưa triển khai. Đoạn cập nhật giai đoạn 1 dưới đây là mốc lịch sử.

**Cập nhật 28/10/2026:** theo phạm vi mới, lượt này chỉ hoàn tất giai đoạn 1
(lõi C07/C08/C10/C11 và tests nghiệp vụ). Kết quả cuối: **849 passed, 0 failed,
0 skipped**; Ruff check/format trên phạm vi giai đoạn 1 đạt. Xem
[checklist có evidence](../group_c_phase1_20261028_193924/checklist.md) và
[checkpoint tiếp tục](../group_c_phase1_20261028_193924/checkpoint.md).
Giai đoạn 2–3 chưa triển khai trong lượt này; wiring/persistence có sẵn từ trước
chưa được xem là đã nghiệm thu.

Nguồn yêu cầu: tệp người dùng ngày 28/10/2026. Không dùng output EXPECTED hoặc
observations tham chiếu làm kết quả. Reference C05/C06/C09 chỉ là input upstream
khi ghi rõ nguồn. Không có lời gọi API trả phí trong phiên triển khai này.

| Yêu cầu | Implementation | Tests / bằng chứng | Trạng thái hiện tại |
|---|---|---|---|
| C07: bốn findings, grounding, review, numeric | `modules/compliance/criterion_reasoner.py`, provider/review/verification helpers | 575 tests; inventory 441 criteria / 7 types / 12 schemas | Giai đoạn 1 đạt |
| C08: policy, missing/unresolved/exclusion | `modules/compliance/requirement_aggregator.py` | 81 tests nghiệp vụ | Giai đoạn 1 đạt |
| C10: hai nhánh, guards, XOR, snapshots/dedup | `modules/risks/` | 110 tests nghiệp vụ riêng | Giai đoạn 1 đạt |
| C11: template mapping, validation, gaps | `modules/recommendations/` | 73 tests nghiệp vụ riêng | Giai đoạn 1 đạt |
| Nối bốn lõi và kiến trúc | Tests unit thuần; không gọi workflow | 8 tests nối lõi + 2 architecture tests | Giai đoạn 1 đạt |
| Workflow + DI | `compliance/service.py`, `workflows/steps_5_7.py`, draft workflow | 26 unit + 7 draft integration tests | Giai đoạn 2 đạt |
| Runner offline/replay/save/read | `modules/assessments/run_group_c.py` | 39 CLI tests; demo saved/read/retry/replay thật | Giai đoạn 2 đạt |
| PostgreSQL | `modules/assessments/repository.py` | 43 integration cases + DB/handoff/snapshot/seed checks; không skip | Giai đoạn 2 đạt |
| Contracts và checks toàn repo | `shared/contracts/`, schemas JSON, Ruff/pytest toàn bộ | 1259 passed, 0 skipped; checksum/Windows regressions | Giai đoạn 3 đạt |
| Tài liệu/gói bàn giao đầy đủ | README, architecture, module guide, docs/group_c_handoff.md | Folder group_c_completion_20261029_172537; source/ZIP/SHA manifests | Giai đoạn 3 đạt; gói được kiểm chứng bằng assemble.py |

Phụ thuộc bên ngoài: upstream OCR/Scope/Temporal/Retrieval/Citation thật, nguồn
chứng từ được xác minh, BackendReview đáng tin, nhãn chuyên gia độc lập. Knowledge
snapshot giữ flags draft/unverified; snapshot không phải phê duyệt pháp lý.
