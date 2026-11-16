# Gold biên soạn trực tiếp bằng suy luận AI — 10/11/2026

Đây là mốc scoped v3 ngày 10/11. Xem [đợt chấm lại 14/11](e2e_gold_reauthored_20261114.md)
để biết đường dữ liệu mặc định mới, 20 ca đã chấm và 340 ca còn chờ; bộ 360 ca
được gắn nhãn GOLD tự động sau mốc này đã bị rút khỏi đường benchmark.

Trạng thái: **SCOPED_GOLD_WITH_FULL_PIPELINE_ADJUDICATION_PENDING**.
`full_e2e_gold_ready=false`; chưa có ca nào hoàn tất Gold toàn bộ pipeline.

Chủ dự án yêu cầu assistant trực tiếp suy luận, không gọi Qwen/API LLM khác.
Đợt này ghi `AI_SOURCE_ADJUDICATED`, `human_legal_signoff=false`. Đây là AI
biên soạn có căn cứ cho benchmark đồ án, không phải chứng thư/chữ ký của một
chuyên gia pháp lý là người thật. Không cần xin lại chấp thuận dùng AI của chủ dự án.

## Nguồn đang dùng

- PDF: `PDF360_DRAFT_GTC_V4_R2_20261110`, 360 file.
- Knowledge: `V750_KNOWLEDGE_OWNER_APPROVED_20261110`.
- Knowledge SHA-256:
  `4ab2d7ea296ea908e25c09fcb6d5f073f1ebe1917678b36390f803b1c725804a`.
- Chỉ dùng PDF, tri thức đã khóa và C01 công khai. Không dùng output của pipeline
  đang chấm để tạo đáp án cho chính nó.

Kết quả local nằm tại:

```text
/home/chienqt/Downloads/legal_compliance_gold_direct_v3_20261110/
```

## Coverage thực tế

| Loại | Số lượng | Giới hạn sử dụng |
| --- | ---: | --- |
| PDF kiểm tra lại checksum | 360 | Xác nhận bytes nguồn, không chứng minh đã đọc hiểu pháp lý toàn văn |
| Trường literal kế thừa và kiểm tra lại | 12.960 | Giá trị phụ lục; không phải facts toàn văn |
| Identity binding mới | 4.149 | Số hiệu khớp duy nhất catalog; chưa phải C09 VALID |
| Identity còn chờ | 420 | UNJUDGED; thiếu catalog không tự là INVALID |
| Chứng cứ hiện diện nguồn | 1.088 | Thành phần evidence, không tự thành C07 SATISFIED |
| Criterion được xét | 104 | 100 SATISFIED, 3 VIOLATED, 1 UNKNOWN do xung đột giá, thuộc 55 PDF |
| Criterion ngoài phạm vi | 107 | Theo DRAFT_REVIEW, không tính thành thiếu căn cứ hay đạt |
| Requirement đủ toàn bộ criterion trong family | 79 | Chỉ family/phạm vi đã khai báo, không phải toàn hợp đồng |
| Assertion loại rủi ro và hành động | 4 mỗi loại | Chưa chấm toàn bộ risk catalog ID/severity hay toàn báo cáo |

Các archetype dương tính do AI biên soạn được script gắn lại vào đúng đoạn
nguồn và kiểm tra quote/offset/hash/ngày. Điều đó không có nghĩa AI đã đọc hiểu
toàn bộ mọi trang của 360 PDF, hoặc đã có hai chuyên gia độc lập đồng thuận.
Không có nhãn MISSING hay khẳng định vắng điều khoản bị cấm được tạo từ top-K rỗng.

## File cho từng người

- `GOLD_DIRECT_MASTER_EVALUATOR.xlsx`: index 360 ca, evaluator giữ riêng.
- `GOLD_DIRECT_DEV_VALIDATION.xlsx`: 240 DEV + 60 VALIDATION; có thể chia sẻ nhóm.
- `GOLD_DIRECT_TEST_EVALUATOR_ONLY.xlsx`: đáp án 60 TEST, không đưa vào TEST INPUTS.
- `AI_LEGAL_REASONING_REPORT.md`: căn cứ, lập luận, cách tái sử dụng và phần còn mở.
- `GOLD_COVERAGE.json`, `VALIDATION.json`, `FULL_RELEASE_GATE.json`: kiểm tra phạm vi.
- `cases/`, `catalog_identity/`, `evidence_components/`, `derived_assertions/`:
  JSON cho đúng các lớp đáp án tương ứng.

Không seed ba workbook đáp án này thay workbook runtime. DB, PDF và manifest
tải dataset của nhóm không thay đổi trong đợt này.

## Những việc chưa hoàn tất

Cần đối chiếu đủ C05/facts/chuyển tiếp, toàn bộ criterion còn áp dụng, các negative
review, relevance pool, citation temporal/domain và đầu ra C08–C13 toàn checklist.
DS453_01/02 còn chờ khóa kết luận điều kiện trả chậm/trả dần; không ép thành
NOT_TRIGGERED hoặc biến annotation chưa làm xong thành UNKNOWN pháp lý.

Evaluator chỉ chấm những target có annotation Gold được khai báo; các target
khác giữ UNJUDGED. Không công bố accuracy end-to-end từ gói có phạm vi này.

Gói [Gold v1 trước đó](gold_answer_set_20261110.md) được giữ nguyên như một mốc
lịch sử, không phải bằng chứng full Gold mới đã hoàn thành.
