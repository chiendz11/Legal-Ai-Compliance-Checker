# Risks — C10

Bước 6 nhận C07 và C09 độc lập, cùng context/knowledge đã pin, rồi tạo C10 qua
`service.evaluate_risks(RiskRequest, knowledge, diagnostics=...)`. Module thuần,
không truy vấn DB, gọi LLM hoặc có HTTP endpoint riêng.

- `compliance_mapper.py` match criterion/finding và guards của C07. Source là
  `C07.ket_qua_id`, gắn đúng requirement instance. C07 cần context, contract và
  knowledge hash; thiếu hoặc lệch pins bị từ chối, không tự gán hash hiện tại.
- `citation_mapper.py` match C09 status/reason/domain, verification và policy guards.
  Source là `C09.finding_id`. C09 không sửa C05/C07/C08 hoặc checklist retrieval.
  Thiếu provenance có diagnostic `C09_PROVENANCE_UNAVAILABLE`; STALE/INVALID không
  được tạo risk khẳng định. UNKNOWN chỉ tạo VERIFICATION khi policy cho phép.
- `policy.py` đọc `quy_tac_rui_ro` và `danh_muc_rui_ro` từ KnowledgeSnapshot, kiểm tra
  enabled/status, catalog/rule identity, rule version và severity. Thiếu/không hiểu
  policy hoặc catalog giữ diagnostics; không tự đoán rule hoặc tăng severity.
- `aggregator.py` hợp nhất và dedup theo source finding + risk catalog ID, giữ mọi
  rule match trong snapshot. Mỗi risk có đúng một source C07 hoặc C09 (XOR).

UNKNOWN không phải VIOLATED. Risk VERIFICATION cần policy/catalog phù hợp và severity
REVIEW_REQUIRED. Snapshots giữ flags draft/unverified; `review_status=PENDING`.
C09 rỗng có diagnostic `C09_INPUT_EMPTY`; workflow còn phân biệt NOT_RUN với nhánh
đã COMPLETED nhưng không có finding.

`evaluate_compliance` ở module compliance chỉ chạy nhánh compliance; pipeline
`workflows.steps_5_7.evaluate` mới nhận C09 và hợp nhất. Store giữ C10 trong
`runtime.ket_qua_rui_ro` cùng full DTO/run lineage. Nhóm D đọc output đã lưu của đúng
case/run, không gọi mapper lại khi dựng report.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q -c backend/pyproject.toml backend/tests/unit/test_risks.py
```

Tests nghiệp vụ bao phủ các findings, citation statuses/domain, ownership/pins,
verification guards, severity, source XOR, rule/catalog gaps, dedup và hai nhánh độc lập.
Xem [bàn giao nhóm C](../../../../../docs/group_c_handoff.md).
