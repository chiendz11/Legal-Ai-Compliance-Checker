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

Metadata hỗ trợ 3 trạng thái minh bạch (không ghi `TEMPLATE_ENGINE_NO_LLM` nếu đã gọi Qwen):
- Chỉ Template Engine (`C11_PERSONALIZATION=off`): `model_version=TEMPLATE_ENGINE_NO_LLM`, `prompt_version=NOT_USED` (`NOT_REQUESTED`).
- Qwen personalization hợp lệ (`C11_PERSONALIZATION=ollama`): `model_version=qwen3.5:9b-q4_K_M@<digest>`, `prompt_version=C11_PERSONALIZATION_V1`, ghi nhận `personalization.status=APPLIED` trong `template_snapshot_json`.
- Lỗi Ollama, timeout, hết budget, audit lỗi hoặc bị Backend Validator reject: `model_version=TEMPLATE_ENGINE_FALLBACK`, `prompt_version=C11_PERSONALIZATION_V1`, giữ nguyên `noi_dung` deterministic và ghi `personalization.status=FALLBACK` (hoặc `SKIPPED_BUDGET`).

`review_status` luôn là `PENDING`. Generation không phê duyệt knowledge hoặc kết quả pháp lý.

## Hybrid Personalization (`personalization/`)

Thư mục `personalization/` bổ sung lớp cá thể hóa diễn đạt tiếng Việt **tùy chọn** phía sau Deterministic Template Engine, tuân thủ hoàn toàn kiến trúc:

1. **Deterministic Template Engine luôn chạy trước (`generator.py`):** quyết định template (`ALL`), `loai_hanh_dong`, `uu_tien`, bindings, 22 `LIMITS` và provenance. Nếu Qwen tắt hoặc lỗi, C11 không phụ thuộc Ollama.
2. **Qwen Local (`OllamaRecommendationClient` — `client.py`):** gọi `/api/tags` để xác nhận model local đã cài và lấy đúng SHA-256 digest (không hardcode, cấm remote/cloud), sau đó gọi tuần tự `/api/chat` (`stream=False`, `think=False`, `temperature=0`, JSON Schema strict) với prompt `C11_PERSONALIZATION_V1`.
3. **Audit X02 (`module="C11"`, `provider="OLLAMA_LOCAL"`):** mỗi lượt gọi thực tế ghi `PostgresLlmAuditSink` (`input_sha256`, `output_sha256`, `schema_version=C11_PERSONALIZED_RECOMMENDATION_V1`, token counts, latency; không lưu raw prompt/response). Nếu audit persistence lỗi → fallback, không chấp nhận kết quả cá thể hóa.
4. **Backend Validator (`personalization/validator.py`):** kiểm tra cấu trúc JSON schema (`extra="forbid", strict=True`), cấm Markdown fence/HTML/vượt độ dài; kiểm tra anchor (số tiền, `%`, ngày, số lượng, số hiệu/tên văn bản, trích dẫn nguyên văn, thực thể/tài khoản, checklist/dự thảo); cấm tự tuyên bố vô hiệu/chế tài/tăng ưu tiên; và chặn tuyệt đối việc biến `UNKNOWN`/`VERIFICATION` thành kết luận vi phạm hay yêu cầu sửa chữa.
5. **Diagnostics & Fallback:** ghi nhận rõ `C11_PERSONALIZATION_DISABLED`, `C11_PERSONALIZATION_CALLED`, `C11_PERSONALIZATION_APPLIED`, `C11_PERSONALIZATION_REJECTED`, `C11_PERSONALIZATION_FALLBACK`, `C11_PERSONALIZATION_BUDGET_EXHAUSTED`, `C11_MODEL_NOT_INSTALLED`, `C11_MODEL_UNAVAILABLE`, `C11_MODEL_TIMEOUT`, `C11_INVALID_STRUCTURED_OUTPUT`, `C11_ANCHOR_MISMATCH`, `C11_UNSAFE_CONTENT`, `C11_AUDIT_PERSISTENCE_FAILED`.

### Cấu hình `.env` & Kiểm thử

```dotenv
C11_PERSONALIZATION=off          # đổi thành ollama để bật Qwen local
C11_OLLAMA_URL=http://127.0.0.1:11434
C11_OLLAMA_MODEL=qwen3.5:9b-q4_K_M
C11_LLM_TIMEOUT_SECONDS=240
C11_LLM_MAX_CALLS=10
C11_LLM_MAX_INPUT_CHARS=12000
C11_LLM_TOTAL_BUDGET_SECONDS=600
```

Chạy test (fake transport & fake audit sink, không gọi network trong CI):

```bash
pytest -q -c backend/pyproject.toml backend/tests/unit/test_recommendations.py backend/tests/unit/test_c11_hybrid_personalization.py
```

Để benchmark thủ công chất lượng diễn đạt, so sánh cặp `(deterministic_text, noi_dung)` trên đủ 4 nhóm `VIOLATED`, `MISSING`, `UNKNOWN/VERIFICATION`, `CITATION`, kiểm tra 100% anchor định lượng/quote/căn cứ còn nguyên và không tuyên bố chất lượng pháp lý tăng chỉ vì văn phong tự nhiên hơn.

Store lưu normalized C11 trong `runtime.khuyen_nghi_danh_gia` và full DTO theo exact
case/run lineage. Khi nhóm D dựng báo cáo, đọc C11 đã lưu cùng C10 instance; không chạy
generator/validator lại. `Store.get/get_lineage` kiểm tra dữ liệu lịch sử mà không gọi
engines.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q -c backend/pyproject.toml backend/tests/unit/test_recommendations.py
```

Tests có mapping/binding, multi-template, required elements/facts, disabled/gaps,
evidence/legal basis, priority, verification-only actions và provenance tampering.
Xem [bàn giao nhóm C](../../../../../docs/modules/group_c_compliance_and_risk.md).
