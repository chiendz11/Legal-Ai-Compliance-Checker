# Checklist nhóm C — giai đoạn 1

Ngày 28/10/2026, múi giờ Asia/Saigon. Phạm vi theo yêu cầu mới nhất của người dùng:
lõi C07/C08/C10/C11 và tests nghiệp vụ. Chưa triển khai giai đoạn 2–3 trong lượt này.
Các sửa đổi chưa commit có từ trước được giữ lại.

| Yêu cầu | Implementation | Tests / bằng chứng | Trạng thái |
|---|---|---|---|
| C07: đủ checklist resolved, bốn findings, grounding và uncertainty | `criterion_reasoner.py`, `grounding_validator.py` | 575 tests C07 trong `pytest.xml`; gồm 43 hardening tests | Đạt |
| C07: proposal/review độc lập, digest/context và registry | `llm_observations.py`, `reviewed_observations.py`, `verification.py` | 49 tests provider + 13 tests review; nằm trong 575 tests C07 | Đạt |
| C07: Decimal, units/denominator/scope/target, policy không hỗ trợ | `numeric_rules.py`, `decision_rules.py` | 206 numeric tests; `knowledge_inventory.json`: 441 criteria / 7 types / 12 schemas | Đạt |
| C08: AGG_CAN_HO_V1, precedence, exclusions, coverage/snapshots | `requirement_aggregator.py` | `test_requirement_aggregator.py`: 81 passed; provenance C07 bắt buộc | Đạt |
| C10: compliance/citation độc lập, guards, source XOR, severity/dedup | `modules/risks/` | `test_risks.py`: 110 passed; missing/foreign pins và C09 provenance | Đạt |
| C11: mapping/instance, multi-template, facts/elements/limits | `modules/recommendations/` | `test_recommendations.py`: 73 passed; missing C07 pins bị từ chối | Đạt |
| Nối các lõi thuần, không dùng workflow/DB | `test_group_c_core.py` | 8 passed: 4 findings × có/không C09; không đổi nhánh compliance | Đạt |
| Kiểm tra cuối trong phạm vi giai đoạn 1 | Bốn lõi và tests liên quan | 849 passed, 0 failed, 0 skipped; Ruff check đạt; format: 18 files đạt | Đạt |
| Giai đoạn 2: workflow/runner/PostgreSQL/demo save-read | Không sửa trong lượt này | Chưa chạy nghiệm thu giai đoạn 2 | Chưa triển khai |
| Giai đoạn 3: toàn bộ checks/schemas/tài liệu/gói bàn giao | Chỉ lưu checklist/checkpoint theo yêu cầu lượt này | Chưa chạy nghiệm thu toàn repo | Chưa triển khai |

Lệnh thực tế và exit codes: `checks.json`; stdout: `pytest_phase1.log`,
`ruff_check_phase1.log`, `ruff_format_phase1.log`. Xem `checkpoint.md` để tiếp tục.
Không coi kiểm thử unit này là bằng chứng workflow/runner/PostgreSQL đã đạt.
