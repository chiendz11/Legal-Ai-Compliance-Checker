# Audit LLM dùng chung — X02

Mỗi module tự cấu hình provider, model, client và prompt. Phần dùng chung tại `backend/src/legal_checker/shared/llm/audit.py` chỉ ghi nhật ký theo contract X02; không gọi LLM, không giữ API key và không tính kết luận pháp lý.

## Các thành phần

| Thành phần | Mục đích |
|---|---|
| `LlmAudit` | Pydantic model X02 trong `shared/contracts/audit.py` |
| `LlmAuditSink.append(event)` | Interface writer; tests có thể inject sink trong bộ nhớ |
| `PostgresLlmAuditSink` | Ghi vào `runtime.nhat_ky_goi_llm`, đọc lại bằng `get(ca_id, lan_goi_id)` |
| `audit_llm_call(...)` | Context manager cho một provider attempt; tạo UUID, hash input, đo latency và ghi SUCCESS/ERROR |
| `call.call_id` | UUID attempt để module liên kết/log/query lại bản audit |
| `call.set_error_code(...)` | Map lỗi SDK sang mã kỹ thuật như RATE_LIMIT; không nhận raw error message |
| `call.complete(...)` | Ghi hash của response thực và usage/cost được báo; phải gọi khi provider trả kết quả |
| `payload_sha256(...)` | Hash text/bytes nguyên trạng hoặc JSON canonical/Pydantic payload |
| `AuditPersistenceError.event` | Metadata cần ghi lại khi provider thành công nhưng DB audit lỗi |

X02 không có `run_id` riêng trong schema hiện tại. Dùng `Context.trace_id` tương ứng run và giữ `ca_id`; không tái sử dụng trace cho các run khác nhau. Context không được ghi nguyên khối vào log, chỉ lấy fields cần thiết.

## Cách module sử dụng

`build_services(settings)` đã cung cấp `services.llm_audit`. Khi khởi tạo service của module, truyền sink này qua constructor/tham số; module không cần mở connection hoặc đọc mật khẩu DB trong engine.

Nếu đang chạy module/test riêng, có thể tạo sink trực tiếp:

```python
from legal_checker.core.config import Settings
from legal_checker.shared.llm.audit import PostgresLlmAuditSink

settings = Settings.from_env()
audit_sink = PostgresLlmAuditSink(settings.database_url)
```

**Case C01 phải được đăng ký trong `runtime.ca_danh_gia` trước khi gọi provider.** Sink không tự tạo case, sửa knowledge hoặc fake dữ liệu đầu vào khi thiếu FK.

Ví dụ dưới đây nhận callback `call_provider` do module triển khai. Callback thực sự gọi SDK của module và trả JSON-serializable dict; đây không phải client dùng chung. Với provider có format usage khác, module map về số token thật trước khi gọi `complete`.

```python
from legal_checker.shared.llm.audit import audit_llm_call


def generate_with_audit(
    *,
    context,
    request_body,
    call_provider,
    audit_sink,
    provider,
    model_version,
    prompt_version,
    schema_version,
    attempt=1,
):
    with audit_llm_call(
        audit_sink,
        context=context,
        module="COMPLIANCE",  # Đổi theo module thực sự gọi.
        provider=provider,
        model_version=model_version,
        prompt_version=prompt_version,
        schema_version=schema_version,
        input_payload=request_body,  # Body thực tế; không đưa headers/API key vào.
        attempt=attempt,
    ) as call:
        response = call_provider(request_body)
        usage = response.get("usage") or {}
        call.complete(
            response,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )
    return response
```

Gọi `complete` ngay sau khi SDK trả response. Parse/validate kết quả nghiệp vụ, evidence, gates và C07/C11 ở bên ngoài context này. `SUCCESS` chỉ nói provider attempt đã trả kết quả và module đã ghi nhận response; không chứng minh đáp án hợp lệ hoặc hợp đồng tuân thủ.

Nếu provider trả Pydantic response, đưa model vào `complete` hoặc chuyển bằng `model_dump(mode="json")`. Payload dict phải JSON-serializable và không có NaN/Infinity. Hàm hash không làm sạch hoặc cắt nội dung trước khi tính hash.

## Quy ước thống nhất cho cả nhóm

- Metadata phải ghi đúng module/provider/model/prompt/schema version thực tế và Context của ca đang chạy. Không đặt API key hoặc nội dung hợp đồng trong các trường metadata.
- Chỉ dùng context cho provider attempt thật. Rule thuần, fixture replay, đọc DB và unit test wiring không tự tạo log LLM thật.
- Không lưu prompt, messages, response body, API key hoặc exception message vào bảng X02. Chỉ lưu hash payload và metadata. `ma_loi` dùng mã kỹ thuật ngắn, không chứa raw error body.
- Token/chi phí chưa được provider hoặc hệ thống billing xác định thì giữ `null`, không tự gán 0. `latency_ms` đo tại client; `ngay_goi` là thời điểm bắt đầu có timezone UTC.
- Có chi phí thật thì truyền `cost=Decimal(...)`, `currency="USD"` hoặc mã tiền tương ứng vào `complete`. Không suy đoán chi phí từ model name. Các giá trị phải không âm.
- Mỗi attempt LLM tạo một `lan_goi_id` riêng. Khi retry provider, mở context mới và tăng `attempt`. Nếu SDK tự retry nội bộ, module cần quản lý/công bố giới hạn đó; helper không quan sát được các HTTP attempts ẩn bên trong SDK.
- Ra khỏi context mà chưa gọi `complete` sẽ ghi ERROR / `RESULT_NOT_RECORDED` và phát sinh `AuditResultMissingError`.
- Khi provider/module phát sinh exception trong context, helper ghi ERROR / `PROVIDER_ERROR`, rồi raise lại exception gốc. Trong handler exception của SDK, có thể gọi `call.set_error_code("RATE_LIMIT")` rồi raise lại lỗi gốc để lưu mã cụ thể. Khi dùng `append` trực tiếp, caller cũng cung cấp mã lỗi theo regex X02.

## Lỗi DB, duplicate và transaction

Sink mở transaction riêng cho mỗi `append`, nên log của provider vẫn có thể được commit dù transaction lưu kết quả nghiệp vụ bị rollback sau đó. Case đã tạo trong transaction khác phải được commit trước để FK nhìn thấy được. Sink không tạo hoặc sửa bảng; áp dụng migrations hiện có bằng `scripts.local_db init`.

Writer chỉ INSERT. Gửi lại cùng một `LlmAudit` với cùng ID và toàn bộ metadata giống nhau là idempotent. Cùng ID nhưng nội dung khác sẽ phát sinh `ConflictError`; không ghi đè bản cũ. `loai_du_lieu` được writer đặt `LIVE_LLM_CALL`, phân biệt với dữ liệu workbook tham chiếu. Đây là quy ước của writer, không phải chứng thực độc lập rằng provider đã được gọi.

Nếu provider đã thành công nhưng DB audit lỗi, helper raise `AuditPersistenceError`; caller có thể retry **ghi event** sau khi DB ổn, không tự gọi lại LLM:

```python
from legal_checker.shared.llm.audit import AuditPersistenceError

try:
    response = generate_with_audit(...)  # Tham số do module cung cấp.
except AuditPersistenceError as error:
    # Giữ error.event trong luồng retry/kiểm soát lỗi của module.
    # Sau khi xử lý nguyên nhân DB, có thể gửi lại nguyên event:
    audit_sink.append(error.event)
    # Exception này không mang response body để phục hồi kết quả nghiệp vụ.
    raise
```

Nếu provider đã lỗi và DB audit cũng lỗi, exception provider gốc vẫn được raise, kèm note báo audit chưa được bảo đảm lưu. Module/workflow phải xử lý tình trạng này; helper không nuốt exception của provider hoặc tự retry network.

## Query trên DB local

```sql
SELECT lan_goi_id, ca_id, module, provider, model_version,
       prompt_version, trang_thai, ma_loi, so_lan_thu,
       input_tokens, output_tokens, latency_ms, chi_phi, don_vi_tien,
       trace_id, ngay_goi
FROM runtime.nhat_ky_goi_llm
WHERE ca_id = 'CA360_001'
ORDER BY ngay_goi, lan_goi_id;
```

Thêm điều kiện `trace_id` khi xem một run. Sink không tự phát hành HTTP endpoint hoặc mở quyền đọc audit cho người dùng khác.

Schema máy đọc: [llm_audit.schema.json](llm_audit.schema.json). Khi đổi X02, cập nhật model, schema này và `contracts/X02.schema.json` trong cùng PR; tests kiểm tra tính nhất quán. Tests mock provider và dùng DB test riêng; không gọi provider thật hoặc yêu cầu API key.
