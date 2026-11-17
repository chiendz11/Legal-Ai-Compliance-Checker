# Dùng OpenAI cho C02, C07 và C11

Ba module giữ nguyên nhiệm vụ và các kiểm tra nghiệp vụ. Có thể chọn API thay
Ollama; API key chỉ nằm trong `.env` local hoặc Kubernetes Secret. Không commit key.

```dotenv
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini-2025-04-14
ASSESSMENT_LLM=openai
DOCUMENTS_EXTRACTOR=hybrid
DOCUMENTS_LLM_PROVIDER=openai
C11_PERSONALIZATION=openai
```

- **C02:** parser/rules/chunker vẫn chạy; API đề xuất facts trong cửa sổ nguồn có
  giới hạn. Backend kiểm quote, vai trò field và đơn vị. Facts mới vẫn
  `DERIVED_REVIEW_PENDING`, không tự trở thành human verified. Facts/conflicts từ
  rules được giữ nguyên. `API_LLM_EXACT_QUOTE_V1` phân biệt với Ollama; tham chiếu
  `API_MODEL` là ID model API, không phải checksum weights.
- **C07:** dùng client OpenAI hiện có, giữ verification, numeric rules, grounding,
  phạm vi và coverage. Giới hạn lượt gọi không phải bằng chứng tài liệu thiếu.
- **C11:** chỉ diễn đạt khuyến nghị từ template đã tạo; validator giữ hành động,
  mức ưu tiên, facts và legal basis. Output sai bị loại và dùng lại template.

Client dùng Responses API structured output và `store=false`; định dạng đúng
schema chưa tự chứng minh kết luận đúng. Audit X02 phân biệt
`DOCUMENT_INTELLIGENCE`, `COMPLIANCE`, `C11`, kèm provider, model, usage và lỗi.
Tham khảo [Structured Outputs của OpenAI](https://developers.openai.com/api/docs/guides/structured-outputs).

Mặc định C02 vẫn chọn Ollama khi bật hybrid và không đặt `DOCUMENTS_LLM_PROVIDER`;
C11 mặc định off. Cấu hình C07 vẫn độc lập. Có thể bật API cho riêng một module.

Đối với demo một lần trên k3d: dùng Secret riêng, ghi lại image/config trước khi
chạy, giữ app/worker/scheduler cùng image, chờ worker cũ dừng rồi mới enqueue.
Sau demo gỡ cấu hình API tạm và Secret demo để không phát sinh lượt gọi trả phí
ngoài ca đã yêu cầu. Giữ nguyên DB, lịch sử, dataset và Secret LLM hiện có.
