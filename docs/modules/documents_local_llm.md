# Document Intelligence hybrid với Qwen local

## Mục đích và phạm vi

Nhánh `feat/documents-local-llm` bổ sung Ollama/Qwen vào trích xuất facts C02.
Parser PDF, structural chunker và citation extractor vẫn giữ nhiệm vụ hiện có.
LLM không quyết định luật áp dụng, không xác nhận hiệu lực citation và không kết
luận tuân thủ. Không cần đổi workbook, PDF, contracts C01–C13 hoặc schema DB.

Model đã có trên host: `qwen3.5:9b-q4_K_M`, digest
`56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.
Ollama native `/api/chat` hỗ trợ JSON Schema qua `format`, sau đó backend vẫn
validate bằng Pydantic. Tham khảo [tài liệu Ollama](https://docs.ollama.com/capabilities/structured-outputs).

## Luồng xử lý

1. Đọc bytes PDF, kiểm hash, parse và dựng chunks nguyên văn như trước.
2. Chạy rules để có profile/facts baseline.
3. Chọn cửa sổ nguồn cho những trường rules chưa có. Mặc định chỉ xét tối đa hai
   cửa sổ, tối đa 1.400 ký tự/cửa sổ. Có thể bật recheck riêng khi so sánh.
4. Qwen trả field/value/quote/source ID trong schema. Tài liệu chỉ là dữ liệu,
   không được dùng làm chỉ thị thay đổi nhiệm vụ.
5. Backend kiểm field cho phép, source ID, quote nguyên văn và giá trị phải có
   trong quote. Số phải có đơn vị phù hợp và là token đầy đủ; không đổi năm thành
   tháng, không suy số tiền hoặc ngày chưa ghi.
6. Ghép facts mới với bằng chứng. Giữ nguyên facts/conflicts đã có từ rules;
   không dùng một đề xuất AI để tự chọn lại kết quả hoặc giải quyết conflict cũ.
7. Version mới khóa theo source/parser/chunker/rules, model digest, prompt/schema,
   cấu hình và output semantic được chấp nhận. Rebuild ID và ánh xạ evidence cùng
   diagnostics sang chunks cuối trước khi writer lưu DB.

Bản v1 hỗ trợ chín tên fact đã được sử dụng trong Documents:

| Fact | Giá trị |
|---|---|
| `warranty_months` | Số tháng bảo hành có ghi rõ |
| `dien_tich` | Diện tích sử dụng căn hộ |
| `gross_area_m2` | Diện tích sàn xây dựng căn hộ |
| `land_area_m2` | Diện tích thửa đất |
| `ten_ben_ban`, `ten_ben_mua` | Tên đúng vai trò, chép từ nguồn |
| `dia_chi_ben_ban`, `dia_chi_ben_mua` | Địa chỉ đúng vai trò, chép từ nguồn |
| `phuong_thuc_thanh_toan` | Phương thức/điều kiện thanh toán chép từ nguồn |

V1 không tự điền typed profile/scope flags, chủ thể hoặc time markers mới từ
suy luận LLM. Các trường đó tiếp tục do rules hiện có tạo. Fact ngữ nghĩa có thể
cung cấp dữ liệu và evidence cho người dev/module tiêu thụ, nhưng cần bước kiểm
chứng nghiệp vụ riêng nếu muốn dùng làm số liệu hoặc điều kiện đã xác minh.

## Trạng thái và giới hạn tin cậy

- Fact LLM mới: `DERIVED_REVIEW_PENDING`, `human_verified=false`.
- Nhiều giá trị LLM khác nhau: `CONFLICT`, giữ các giá trị và quote tương ứng.
- `phuong_phap=LOCAL_LLM_EXACT_QUOTE_V1@<model_digest>` để truy vết.
- Quote đúng chỉ chứng minh dữ kiện có nguồn; chưa tự chứng minh model chọn đúng
  ý nghĩa/vai trò. SourceFactVerifier hiện chỉ nhận facts `EXTRACTED`, vì thế
  những đề xuất pending này không tự được nâng thành số liệu verified ở C07.
- Response rỗng hoặc hết ngân sách không chứng minh nội dung vắng toàn văn;
  không tạo MISSING/UNKNOWN pháp lý từ việc chưa đọc phần còn lại.
- Chế độ hybrid không thêm OCR. PDF scan không text vẫn phải xử lý lỗi đọc như trước.

## Cấu hình host

Cài backend với extra `ai` trong môi trường ảo. Khởi động model đã tải:

```bash
bash /home/chienqt/Dev/newBTL/local-models/ollama/serve.sh
```

Giữ cấu hình DB/knowledge/API key hiện có; chỉ thêm/sửa các biến Documents:

```dotenv
DOCUMENTS_EXTRACTOR=hybrid
DOCUMENTS_OLLAMA_URL=http://127.0.0.1:11434
DOCUMENTS_OLLAMA_MODEL=qwen3.5:9b-q4_K_M
DOCUMENTS_LLM_MAX_CALLS=2
DOCUMENTS_LLM_TIMEOUT_SECONDS=240
DOCUMENTS_LLM_RECHECK_EXISTING=off
```

`ASSESSMENT_MODULES=modules` dùng Documents thật. `ASSESSMENT_LLM` vẫn cấu hình
riêng cho Compliance: bật Documents hybrid không tự bật, tắt hoặc đổi C07 provider.
Khởi động lại backend/worker để đọc cấu hình mới. Mặc định `.env.example` vẫn dùng
rules; mỗi người bật hybrid khi đã có model phù hợp. Để quay lại baseline, đặt
`DOCUMENTS_EXTRACTOR=rules` rồi khởi động lại.

Local model không được tự khởi động hoặc tải thêm bởi ứng dụng. `/api/tags` phải
có đúng model local; model remote hoặc cloud không được dùng làm fallback.
Ollama options mặc định: context 4.096, output tối đa 512 token, temperature 0,
seed 42, bốn CPU threads, `think=false`, tuần tự. Model digest pin trong client
được lấy lại khi khởi tạo backend/worker mới.

Localhost trong pod/container không phải localhost host. Bản này chạy trên host;
muốn dùng k3d cần cấu hình đường mạng tới Ollama và URL phù hợp. Không tự mở server
ra mọi interface hoặc thay đổi GitOps trong đợt này.

## Audit, cache và lỗi

Mọi lượt `/api/chat` thực tế trong workflow ghi X02 bằng audit sink chung, với
provider `OLLAMA_LOCAL`, module `DOCUMENT_INTELLIGENCE`, model/digest,
prompt/schema, input/output hashes, trace, token usage nếu provider có và latency.
Không lưu prompt/API key vào X02 và không giả chi phí 0. Cache hit không tạo lượt
LLM gọi giả.

Cache response ở `SOURCE_CACHE_DIR/documents_llm/`, khóa theo input, source,
model digest, options và prompt/schema; checksum được kiểm trước khi dùng lại.
Quote/schema vẫn được validate khi đọc cache. Cache có thể chứa quote hợp đồng;
giữ trong storage private và không commit Git.

Diagnostics trong run/report phân biệt `DOCUMENT_LLM_CALLED`,
`DOCUMENT_LLM_CACHE_HIT`, `DOCUMENT_LLM_BUDGET_LIMIT`,
`DOCUMENT_LLM_NO_CANDIDATE_WINDOWS`, quote/unit/field/source invalid và lỗi model.
Timeout/mất server/model không có sẽ giữ rules output kèm diagnostic; không
âm thầm dùng reference QA. Lỗi ghi audit không được coi như audit thành công.
Ngân sách thời gian chặn việc bắt đầu cửa sổ tiếp theo; timeout HTTP không phải
cam kết hủy ngay tác vụ đang chạy trên server.

## Kiểm tra

```bash
pytest -q -c backend/pyproject.toml backend/tests/unit/test_document_semantic_extractor.py
```

Tests dùng transport/model giả để kiểm các điều kiện chấp nhận/reject, conflict,
version/provenance/cache và audit, không gọi model trong CI. Đợt thử local có một
PDF ngắn cho câu thời hạn đứng trước “bảo hành”, cùng PDF v4r2 HD360_001.
Kết quả smoke nằm ngoài Git ở `data/private/documents_local_llm_20261116/`.
Không dùng hai smoke này làm bằng chứng hybrid tốt hơn rules trên 360 hợp đồng.
Benchmark chất lượng cần cùng PDF/Gold scope, split, cấu hình và các số đo độc lập.
