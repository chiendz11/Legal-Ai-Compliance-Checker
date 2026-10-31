# Recommendations — C11

Bước 7 đã triển khai `service.generate_recommendations(RecommendationRequest,
knowledge, diagnostics=...)`. Module tạo nội dung bằng templates đã pin, không gọi LLM
và không có HTTP endpoint riêng.

`validator.py` kiểm tra C10 context/provenance, source C07/C09 và pinned rule matches
bằng policy C10 thuần; không chạy lại reasoning. `generator.py` lấy mapping
`rui_ro_khuyen_nghi` theo `C10.rui_ro_id`, rồi bind mỗi C11 vào đúng risk instance
`C10.ket_qua_rui_ro_id`.

- Selection policy hiện hỗ trợ **ALL**: render mọi template được map, theo thứ tự xác
  định; mapping trùng cùng template được gộp và giữ provenance. Không lấy template đầu
  tùy ý. Policy khác tạo diagnostic, không đoán cách chọn.
- `required_elements_json` hỗ trợ checklist prose hoặc `{fields, text}`; field bắt buộc
  phải có binding thật. `gioi_han_sinh_json` chỉ chấp nhận allowlist constraints đã hỗ
  trợ. Thiếu mapping/template/facts, disabled template, policy lạ hoặc JSON lỗi đều có
  diagnostics.
- Chỉ render tên field trực tiếp được hỗ trợ; không attribute/index/expression hoặc
  tự bịa luật, ngày, tiền, tên người, tài khoản. Placeholder văn bản từ template được
  giữ nguyên. Nội dung “khi áp dụng” không biến thành mọi điều kiện đều bắt buộc.
- Giữ action, priority không vượt severity C10, evidence/legal basis, conditions,
  mapping/template/risk snapshots, rule version và knowledge hash. UNKNOWN/VERIFICATION
  chỉ có verification actions với REVIEW_REQUIRED và ghi đúng thông tin cần làm rõ.

Metadata luôn là `model_version=TEMPLATE_ENGINE_NO_LLM`, `prompt_version=NOT_USED`,
`review_status=PENDING`. Generation không phê duyệt knowledge hoặc kết quả pháp lý.

Store lưu normalized C11 trong `runtime.khuyen_nghi_danh_gia` và full DTO theo exact
case/run lineage. Khi nhóm D dựng báo cáo, đọc C11 đã lưu cùng C10 instance; không chạy
generator/validator lại. `Store.get/get_lineage` kiểm tra dữ liệu lịch sử mà không gọi
engines.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q -c backend/pyproject.toml backend/tests/unit/test_recommendations.py
```

Tests có mapping/binding, multi-template, required elements/facts, disabled/gaps,
evidence/legal basis, priority, verification-only actions và provenance tampering.
Xem [bàn giao nhóm C](../../../../../docs/group_c_handoff.md).
