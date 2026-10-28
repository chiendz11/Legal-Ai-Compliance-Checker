# Checklist nhóm C — triển khai theo giai đoạn

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

| Yêu cầu | Implementation | Tests / bằng chứng | Trạng thái sau giai đoạn 1 |
|---|---|---|---|
| C07: bốn findings, grounding, review, numeric | `modules/compliance/criterion_reasoner.py`, provider/review/verification helpers | 575 tests; inventory 441 criteria / 7 types / 12 schemas | Giai đoạn 1 đạt |
| C08: policy, missing/unresolved/exclusion | `modules/compliance/requirement_aggregator.py` | 81 tests nghiệp vụ | Giai đoạn 1 đạt |
| C10: hai nhánh, guards, XOR, snapshots/dedup | `modules/risks/` | 110 tests nghiệp vụ riêng | Giai đoạn 1 đạt |
| C11: template mapping, validation, gaps | `modules/recommendations/` | 73 tests nghiệp vụ riêng | Giai đoạn 1 đạt |
| Nối bốn lõi và kiến trúc | Tests unit thuần; không gọi workflow | 8 tests nối lõi + 2 architecture tests | Giai đoạn 1 đạt |
| Workflow + DI | `compliance/service.py`, `workflows/steps_5_7.py`, draft workflow | Pipeline và upstream adapter tests | Giai đoạn 2 chưa triển khai/nghiệm thu |
| Runner offline/replay/save/read | `modules/assessments/run_group_c.py` | CLI artifacts và demo local | Giai đoạn 2 chưa triển khai/nghiệm thu |
| PostgreSQL | `modules/assessments/repository.py` | Save/read, lineage, rollback, retry, conflict, history | Giai đoạn 2 chưa triển khai/nghiệm thu |
| Contracts và checks toàn repo | `shared/contracts/`, schemas JSON, Ruff/pytest toàn bộ | Schema drift, SQL checksum, cache concurrency, ZIP paths | Giai đoạn 3 chưa triển khai/nghiệm thu |
| Tài liệu/gói bàn giao đầy đủ | README, architecture, module guide | Hướng dẫn/demo/save-read/checks toàn bộ | Giai đoạn 3 chưa triển khai; đã lưu checkpoint giai đoạn 1 |

Phụ thuộc bên ngoài: upstream OCR/Scope/Temporal/Retrieval/Citation thật, nguồn
chứng từ được xác minh, BackendReview đáng tin, nhãn chuyên gia độc lập. Knowledge
snapshot giữ flags draft/unverified; snapshot không phải phê duyệt pháp lý.
