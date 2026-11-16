# Chuẩn hóa báo cáo và tối ưu ngữ cảnh LLM — 09/11/2026

Đợt sửa xử lý các phát hiện sau demo baseline v3: nhãn độ phủ, trạng thái giữa các
tab/export, placeholder khuyến nghị và việc gửi lặp tài liệu cho LLM.

## 1. Cách thiết kế

Giữ nguyên kiến trúc modular monolith, C01–C13 và lịch sử review. Bổ sung
[REPORT_PRESENTATION_V1](../contracts/report_presentation.md) làm contract HTTP
chỉ đọc ngoài C13. Backend và export dùng một projector; FE nhận kết quả đó thay
vì suy luận riêng từ mỗi enum. Không sửa status/gates/hash để xóa cảnh báo.

Nghiên cứu [ContractNLI](https://arxiv.org/abs/2110.01799) tách suy luận trên hợp đồng
và xác định evidence spans; có phân biệt hỗ trợ, mâu thuẫn và không đề cập.
Thiết kế ở đây áp dụng nguyên tắc giữ kết luận có evidence và phân biệt thiếu
thông tin, không xem đây là một tiêu chuẩn pháp lý hoặc bằng chứng accuracy.

## 2. Những phần đã sửa

| Phần | Thay đổi |
| --- | --- |
| Coverage | Tách độ đầy đủ kết quả criterion khỏi độ phủ bằng chứng toàn văn; giữ null với snapshot legacy |
| Review | Dùng disposition giống tab Tuân thủ, giữ enum máy và before/after bên dưới |
| Audit | Taxonomy riêng cho ngoài phạm vi/không phát sinh; dữ liệu gốc vẫn xem được |
| Export | C05 không áp dụng không hiện thành lỗi thiếu version; dùng cùng coverage và C11 projection với FE |
| C11 | Bind nguyên văn/lý do thiếu từ finding/source occurrence; giữ template gốc; không bịa phiên bản luật hoặc thông tin giao dịch |
| Citation progress | Chạy nhánh C09 sau Scope/Temporal, trước phần LLM dài; vẫn chỉ ghép với Compliance tại Risk/Report |
| Retrieval progress | Kết thúc stage sau retrieval đầu; full-text semantic refinement được tính trong Compliance |

## 3. Tối ưu LLM không bỏ nội dung

Semantic batch dùng `SHARED_SOURCE_QUOTE_LINES_V1`: mỗi chunk nguyên văn xuất hiện
một lần trong `source_catalog`; từng item có danh sách Q → line riêng. Giữ nguyên
thứ tự, dòng trống/ngắn, ký tự Unicode và source IDs. Response vẫn được validate
bằng package gốc; quote không thuộc item bị từ chối dù nằm trong cùng request.

Batch được giới hạn theo **kích thước request chung**, không chỉ từng criterion.
Một item quá lớn không được âm thầm cắt; trả CONTEXT_LIMIT. Prompt mới là
`C07_SEMANTIC_V14`, schema transport `BATCH_SHARED_SOURCE_V3`.

Full-document review `C07_FULL_DOCUMENT_REVIEW_V6` tăng trần criterion/request
nhưng tự giới hạn theo output-token budget của client; mặc định tối đa 24.
Các criterion cùng điều luật dùng `legal_article_ref` tới một bản nguyên văn.
Vẫn phải trả đủ mọi ô criterion × source batch. Khi response thiếu/schema sai,
giữ repair và adaptive split; không lưu chứng nhận độ phủ từ ma trận chưa đủ.
Budget criterion analyses và kiểm nguồn/hash vẫn giữ nguyên.

Google có [cơ chế context caching](https://ai.google.dev/gemini-api/docs/caching)
cho nội dung lặp, nhưng phụ thuộc provider/model/API. Đợt này giảm dữ liệu lặp
ngay ở ứng dụng; không giả định endpoint tương thích OpenAI đang hỗ trợ cache
đặc thù của Gemini và không báo token cache chưa đo được.

Retry có giới hạn và audit từng attempt tiếp tục giữ nguyên. Không tăng concurrency
gọi model để che giới hạn tốc độ của tài khoản. Lỗi provider sau khi hết retry vẫn
thành lỗi xử lý/UNKNOWN có lý do, không biến thành hợp đồng vi phạm.

## 4. Kiểm tra và kết quả triển khai

Đã chạy full backend suite: **1.461 pass, 198 skip**. Các test skip phụ thuộc cấu
hình/môi trường hoặc dữ liệu chưa cung cấp; không gọi chúng là pass. Sau điều chỉnh
renderer bổ sung, 83 test liên quan tiếp tục pass; lint/format, kiểm contracts/docs
37 test và frontend typecheck/build đều pass. Hai Dockerfile hiện có build được.

Kiểm lại báo cáo cũ bằng browser: **12/12 kiểm tra pass**, gồm coverage, review,
audit, C11 và JSON C13 giữ nguyên. Chạy mới qua upload/UI → API → Celery → modules/
LLM → report, không replay QA. Đã mở tám tab, kiểm PDF nguồn và export PDF/DOCX/JSON;
không ghi nhận JS exception hoặc HTTP lỗi trong chuỗi kiểm. PDF xuất có 52 trang.

| Thông tin run mới | Giá trị |
| --- | --- |
| Case | CA_UP_8A2D4CDFB11C |
| Run | RUN_5a7bfcb5b45f45eea033ff3b15b77c77 |
| Report | REPORT_1f1d4679-8de3-5a50-a0eb-2394510f57d8 |
| Thời gian | 20:30:45–20:36:48 ngày 09/11/2026, giờ Việt Nam |
| PDF/knowledge | Cùng baseline v3 và hash knowledge với run đối chiếu trước |
| Backend/API/worker/Beat | legal-local/backend:image-2ae8e67b4b4143bdba249c8e837d92d3460cbbb3ab0f3f043489d59e8b264ce2 |
| Frontend | legal-local/frontend:image-c515ed35557895a4bb32777acf68cc49532bd4f370ae41a44aeef57b76697f36 |

[Mở báo cáo mới](http://app.legal-checker.localhost:18880/reports/REPORT_1f1d4679-8de3-5a50-a0eb-2394510f57d8?tab=compliance).
Đây là image build/import local, chưa commit/push hoặc publish GHCR. Argo automated
sync giữ trạng thái tạm dừng như trước; không gọi triển khai này là revision Git đã Synced.

### 4.1 Số đo hiệu năng thật

| Metric | Run trước | Run mới | Thay đổi |
| --- | ---: | ---: | ---: |
| Thời gian INTAKE → COMPLETED | 588,39 giây | 363,28 giây | Giảm 38,26% |
| Input tokens provider báo cáo | 1.604.764 | 1.081.197 | Giảm 32,63% |
| HTTP attempts, gồm retry | 50 | 36 | Giảm 28% |
| SUCCESS | 41 | 34 | |
| ERROR attempts | 9 | 2 | Hai lỗi HTTP tạm thời đã retry phục hồi |
| Semantic repair thành công | 5 | 3 | Không xóa audit của response cần sửa |
| Full-document request thành công | 20 | 12 | Cùng 55 criterion × 4 source batches |

Đây là so sánh **một cặp run**, không phải cam kết độ trễ/chi phí mọi tài liệu hoặc
hóa đơn provider. Chưa đo giá tiền hoặc cached tokens. Benchmark serialization
riêng trên cùng 59 input C06 cũ giảm 32,05% số ký tự payload; bản benchmark bỏ cùng
các verifications/registrations ở cả hai phía, nên không thay số đo token thật.
Do giới hạn theo request chung, số batch semantic có thể tăng; tổng input/HTTP vẫn
giảm trong run đã đo. Không bỏ criterion hoặc cắt source text để đạt số này.

### 4.2 Nhất quán dữ liệu và giới hạn chất lượng

25 kiểm tra handoff đều pass; 244 quote C07 khớp text/offset. Full-document artifact
đúng context/source/hash cho 131 chunks và đủ ma trận 55 criterion qua 4 batch.
C08 tái tổng hợp từ C05/C07 ra đúng kết quả đã lưu. Đây là kiểm nhất quán bằng cùng
engine, không phải gold đánh giá pháp lý độc lập. 22 report lịch sử giữ nguyên hash/JSON.

Run mới có 58 COMPLIANT, 1 NON_COMPLIANT, 1 INSUFFICIENT, 14 ngoài phạm vi và 1
không phát sinh điều kiện. C07 có 84 SATISFIED, 1 VIOLATED, 1 UNKNOWN, 39 ngoài
phạm vi và 4 excluded khác. C09 vẫn 10 VALID/1 UNKNOWN. Không đổi các kết luận này
để ép phân phối giống run trước.

**Chưa nghiệm thu độ đúng của hai kết luận máy thay đổi:**

- `TC_PV_DS436_01`: mới UNKNOWN về phương thức giao tài sản. Run cũ từng SATISFIED
  nhưng quote là phương thức thông báo Fax/thư/điện tín. Quote đó tồn tại thật nhưng
  chưa tự chứng minh phương thức bàn giao căn hộ. Cần đối chiếu evidence bàn giao,
  nội dung mặc định và giới hạn của đúng Điều 436 đã pin; không lấy nhãn cũ làm gold.
- `TC_PV_DS453_02`: mới VIOLATED với quote về bên bán giữ quyền sở hữu đến lúc thanh
  toán đủ. LLM đồng thời phân giải điều kiện trả chậm/trả dần khác run trước. Chưa
  chấp nhận quote này tự nó chứng minh vi phạm; cần rà chính điều kiện Điều 453,
  phân biệt tiến độ ứng tiền với mua chịu và đối chiếu predicate/ngoại lệ. Đây là
  kết luận máy chờ reviewer, không phải phát hiện vi phạm pháp lý đã được xác nhận.

Một phần mục tiêu đợt này đã kiểm được: hiển thị không đánh đồng các loại UNKNOWN,
không còn slot rỗng trên UI/export, và giảm ngữ cảnh có số đo. **Chưa được dùng kết
quả này để khẳng định tăng batch không ảnh hưởng accuracy hoặc toàn catalog đã đúng.**
Trước khi công bố chất lượng/đưa tối ưu này vào release khách hàng, phải chạy tập
DEV/VALIDATION có nhãn độc lập và nghiệm thu riêng condition applicability, predicate
entailment, Recall@K và adverse findings; không dùng phép tái tổng hợp làm gold.

### 4.3 Bằng chứng để tái kiểm

Thư mục ngoài Git:

```text
data/private/report_consistency_20261109/run_01/
```

Các file chính: `comparison_metrics.json`, `payload_benchmark.json`,
`existing_ui_checks.json`, `extended_inspection.json`, `artifact_checks.json`,
`runtime_probe.json`, `browser_checks.json`, các screenshots và report exports.

Workbook, PDF, dataset manifest, seed và các báo cáo cũ giữ nguyên. Không phát hành
lại dataset chỉ vì sửa cách trình bày và transport LLM. Chưa tự review/publish hoặc
khẳng định toàn corpus đạt chất lượng pháp lý.
