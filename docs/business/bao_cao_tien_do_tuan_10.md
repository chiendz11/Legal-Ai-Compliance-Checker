# Báo cáo tuần 10 — Hoàn thiện Inference MVP và chuẩn bị đánh giá đa tình huống

## Mục tiêu

Hoàn thiện luồng xử lý từ PDF hợp đồng đến báo cáo trên Web; bổ sung xử lý các tình huống đủ thông tin, thiếu thông tin, điều khoản bất lợi và dữ liệu mâu thuẫn. Chuẩn bị dữ liệu và các điều kiện cần thiết để kiểm thử, đánh giá định lượng ở giai đoạn tiếp theo.

Báo cáo phân biệt chức năng đã triển khai, kiểm tra đã có bằng chứng và phần cần nghiệm thu tiếp. Không tuyên bố đã benchmark toàn bộ 360 hợp đồng hoặc hoàn thành mọi tiêu chí bàn giao tuần 10.

## 1. Dữ liệu phục vụ phát triển và kiểm thử

- Đã xây dựng bộ **PDF360 v4r2** từ 90 họ mẫu hợp đồng, mỗi họ có bốn biến thể synthetic: S01 — baseline dự thảo; S02 — cố tình bỏ một số thông tin; S03 — điều khoản bất lợi/vi phạm được thiết kế; S04 — dữ liệu mâu thuẫn giữa các phần của tài liệu.
- Chia dữ liệu theo họ nguồn thành **240 DEV / 60 VALIDATION / 60 TEST**. Các biến thể của cùng một mẫu được giữ trong cùng split để giảm rò rỉ từ mẫu nguồn. Việc chia theo họ không tự chứng minh mọi nguồn khác họ đều không gần trùng nhau.
- Có **knowledge pháp lý** gồm văn bản, điều khoản, yêu cầu, phiên bản, phạm vi áp dụng, tiêu chí, decision rules, risk rules và mẫu khuyến nghị.
- Có **workbook runtime/QA** và công cụ seed PostgreSQL local để các thành viên phát triển module độc lập bằng đầu vào tham chiếu, không phải chờ tất cả module phía trước hoàn thành.
- Có đối chiếu nguồn trong phạm vi công bố và các ca kiểm thử rule để kiểm extraction, schema, nguồn và quy tắc nghiệp vụ. Các output tham chiếu do engine sinh vẫn là SILVER, không tự trở thành Gold để chấm chính engine đó.

**Giới hạn:** PDF là dữ liệu giả lập từ mẫu nguồn, không phải 360 giao dịch khách hàng thực tế. S01 là baseline được thiết kế hướng tới đầy đủ, không bảo đảm mọi criterion đều tuân thủ. S03 cần chấm từng criterion để phân biệt bất lợi với vi phạm pháp luật. Việc bỏ dữ liệu ở phụ lục S02 cũng chưa chứng minh toàn văn không có dữ kiện đó. Số trang thay đổi theo mẫu, không mô tả toàn bộ là 30–60 trang/file.

## 2. Các module xử lý hợp đồng và đánh giá pháp lý

### Document Intelligence — C01–C03

- Có luồng tiếp nhận PDF, đọc tài liệu có text layer, trích hồ sơ hợp đồng, facts, chunks và viện dẫn.
- Đã bổ sung xử lý thông tin trong phụ lục, giá, bảo hành, tài khoản và dữ kiện mâu thuẫn.
- Giữ quote, trang, vị trí và hash nguồn để các module sau có thể kiểm tra lại bằng chứng.
- Cần tiếp tục đo độ phủ trên nhiều mẫu. OCR cho PDF scan chưa triển khai; không tuyên bố đọc đúng mọi bảng biểu hoặc bảo toàn toàn bộ văn bản chỉ từ một demo.

### Applicable Law, Citation Validation và Retrieval — C04–C06, C09

- Có Scope/Temporal Resolver xác định yêu cầu và phiên bản dựa trên hồ sơ, loại mốc thời gian, dữ kiện chuyển tiếp và knowledge đã khóa. Không coi ngày ký là mốc duy nhất cho mọi yêu cầu.
- Citation Validation kiểm viện dẫn ở nhánh riêng; cảnh báo viện dẫn không tự trở thành vi phạm nội dung hợp đồng.
- Retrieval tìm evidence theo criterion và mở ngữ cảnh liên quan trong hợp đồng/phụ lục, giữ nguồn để reasoning kiểm tra.
- Đã xử lý các lỗi cụ thể như nhầm nội dung thông báo với phương thức bàn giao. Chưa kết luận mọi evidence đều được xếp đúng Top-1.

### Compliance, Risk và Recommendation — C07–C08, C10–C11

- Có luồng kết hợp rules/số học, đề xuất ngữ nghĩa bằng LLM và kiểm tra bằng chứng trước khi tổng hợp.
- Finding của criterion theo contract là **SATISFIED, MISSING, VIOLATED, UNKNOWN**. Ngoài phạm vi rà soát hoặc không phát sinh điều kiện được biểu diễn riêng, không gọi là một finding thay cho MISSING.
- Có kiểm quote, điều kiện áp dụng, coverage và dữ kiện; dữ liệu thiếu/mâu thuẫn hoặc lỗi xử lý phải có lý do rõ.
- Risk và Recommendation giữ liên kết với requirement, criterion và nguồn; không ép mọi baseline thành tuân thủ để làm đẹp demo.

## 3. Luồng Web End-to-End và báo cáo

- Có luồng upload → tạo ca/run → queue xử lý → các module → lưu báo cáo → hiển thị trên Web.
- Có Celery/Redis và theo dõi tiến độ qua SSE/polling; giao diện đối chiếu PDF với findings/evidence.
- Có code Reviewer Workbench, audit quyết định rà soát C12 và báo cáo C13; review/publish cần nghiệm thu theo hành trình riêng.
- Có chức năng export và biên bản demo kiểm tra JSON/PDF/DOCX. Không suy từ export HTTP 200 thành toàn bộ sản phẩm đã được nghiệm thu.

## 4. Hạ tầng local và giám sát

- Có cấu hình k3d local, Terraform, Argo CD GitOps và các thành phần giám sát Prometheus/Grafana.
- Có cấu hình API, worker, scheduler, PostgreSQL/Redis và autoscaling phục vụ môi trường thử nghiệm.
- Có biên bản triển khai local trước đây. Manifest và pod hoạt động chưa thay bằng chứng autoscaling dưới tải, dựng lại từ checkout mới hoặc nghiệm thu production.

## 5. Kết quả kiểm tra đã có và giới hạn

[Biên bản demo ngày 10/11](../guides/baseline_v4_acceptance_20261110.md) ghi nhận PDF HD360_001 chạy thật qua UI, queue và các module tới báo cáo:

- Run: `RUN_dfd704ad7c3c455ab067d07534bb76dc`.
- Report: `REPORT_48da32fb-461e-579f-9fe8-c811f1f08b42`.
- Đã kiểm tám tab, nguồn PDF và export; biên bản lưu source/knowledge/extractor tương ứng.
- Các lỗi HTTP tạm thời trong run có ghi audit và đã phục hồi qua retry.

Đây là bằng chứng cho ca và phiên bản ghi trong biên bản, không phải benchmark toàn bộ corpus. Không đưa các số 100%, MRR = 1 hoặc Macro-F1 = 1 của bản báo cáo cũ vào kết quả chính thức khi chưa có đủ artifact, phạm vi chấm và nguồn gốc đáp án tương ứng. Điều này không phủ nhận mọi phép đo scoped; phép đo nào đủ hồ sơ thì báo đúng phạm vi đó.

## 6. Công việc chuyển tiếp

1. Chọn và nghiệm thu 5–8 ca DEV đại diện, lưu kết quả từng tình huống, source/knowledge/code pins và lỗi còn mở.
2. Hoàn thiện xử lý thiếu/mâu thuẫn, chọn evidence và phân biệt lỗi provider với thiếu căn cứ pháp lý.
3. Tuần 11: ổn định interfaces, data/seed/CI, auth/review, retry/idempotency và QA modules; sửa lỗi theo bằng chứng.
4. Chuẩn bị benchmark: khóa đáp án trong phạm vi sẽ chấm, bộ chỉ số và cấu hình chạy; tách rõ technical checks với đánh giá chất lượng pháp lý.
5. Tuần 12–13: hoàn thiện chức năng sản phẩm, chạy đánh giá theo phạm vi đáp án đủ điều kiện và nghiệm thu cuối. Chưa đủ Gold toàn bộ thì công bố benchmark theo subset, không tuyên bố kết quả cho toàn bộ 360 ca.

---

## Ghi chú hiện trạng dataset tại ngày 16/11/2026

Phần này giải thích bộ dữ liệu đang có, **không tính tiến độ biên soạn sau tuần 10 thành thành tích tuần 10**.

| Thành phần | Đang có gì? | Dùng làm gì? |
|---|---|---|
| PDF360 v4r2 | 360 PDF synthetic từ 90 họ × 4 biến thể | Đầu vào cho Documents và chạy pipeline thật |
| Knowledge snapshot | Luật/yêu cầu/version/criteria/rules/risk/templates, khóa theo hash | Tri thức dùng chung cho các module; phê duyệt knowledge khác phê duyệt output mới |
| Runtime/QA workbook | Input/output tham chiếu, nguồn và liên kết giữa bảng; nhiều output là SILVER | Seed DB local, JOIN đúng dữ liệu và phát triển song song |
| 32 rule regression cases | Ca kiểm quy tắc và ngưỡng | Kiểm rules/gates; không thay cho 360 đáp án pháp lý |
| Scoped answers | Đáp án cho các câu hỏi/phạm vi đã công bố, ví dụ literal trong phụ lục | Chấm đúng phạm vi đó; không coi là Gold toàn văn |
| Gold Master R12 | 220/360 ca đã biên soạn, 140 ca còn chờ; `full_e2e_gold_ready=false` | Nguồn đáp án nhiều lớp của evaluator; chấm theo coverage/pool đã công bố |

Gold R12 ghi `AI_SOURCE_ADJUDICATED`, `human_legal_signoff=false`; không gọi là bộ được chuyên gia pháp lý con người thẩm định độc lập. Đáp án TEST được đóng gói riêng cho evaluator, nhưng chưa chứng minh mọi người đã giữ kín hoặc đã có blind benchmark độc lập.

[Manifest dataset](../../configs/dataset_dev_validation.json) hiện trỏ phiên bản `v7.5.0-pdf360-v4r2-runtime-20261110`, trạng thái `LOCAL_ARCHIVE_READY`, URL tải còn rỗng. Đây là phiên bản cấu hình dùng cho phát triển; chưa kiểm live DB đang chạy trong đợt sửa báo cáo.

## Benchmark trong kế hoạch và phần nên làm rõ

Workbook đã có:

- Sheet05, dòng10 — tuần11: “benchmark kỹ thuật”, unknown/grounding, auth/job errors/retries.
- Sheet05, dòng12 và sheet02 dòng51–53 — tuần13: metrics Document/Legal/Retrieval/Reasoning, gồm accuracy, Recall@K và F1 theo nhãn thực có.

Vì vậy kế hoạch không thiếu hoàn toàn đánh giá, nhưng còn thiếu một hạng mục benchmark có đầu vào, quy trình, owner, đầu ra và tiêu chí đóng rõ ràng. Nên bổ sung:

| Mốc đề xuất | Việc làm | Owner/đầu ra |
|---|---|---|
| Tuần11 | Khóa dataset/Gold coverage, metric protocol; dựng evaluator, QA kỹ thuật trên DEV | Người1 giữ release; 2–4 định nghĩa metric module; 5 nối runner/artifacts |
| Tuần12 | Chạy VALIDATION, phân tích lỗi, sửa dựa DEV rồi đo lại; ghi mọi lần thay đổi | Từng owner báo lỗi/chi phí/latency; không dùng nhãn VALIDATION để học luật đặc thù rồi gọi kết quả độc lập |
| Tuần13 | Freeze code/model/prompt; chạy TEST một lần chính thức theo protocol; công bố kết quả và giới hạn | Người5 điều phối; evaluator giữ đáp án TEST; cả nhóm bàn giao báo cáo |

Nếu đáp án hoặc nội dung TEST đã được dùng để sửa hệ thống, cần khai báo phần bị ảnh hưởng và dùng holdout mới khi muốn công bố đánh giá blind độc lập. Không thể khôi phục tính blind chỉ bằng cách đổi tên gói.

Chưa sửa workbook kế hoạch trong đợt này. Đề xuất là làm rõ hạng mục benchmark, không đưa số đo chưa có bằng chứng vào báo cáo tuần10.

## Tài liệu liên quan

- [Kế hoạch gốc](ke_hoach_10_tuan.xlsx).
- [Dataset PDF360 v4r2 và runtime](../guides/dataset_pdf360_v4r2_runtime_20261110.md).
- [Gold Master hiện hành](../guides/gold_master_20261114.md).
- [Playbook tích hợp năm người](../guides/parallel_development_playbook.md).
- [PowerPoint tuần10 theo kế hoạch MVP](slides/bao_cao_tien_do_tuan_10.pptx) · [PDF](slides/bao_cao_tien_do_tuan_10.pdf). Slide đã đồng bộ phần MVP, dataset và điều kiện benchmark với báo cáo này vào ngày 16/11/2026.

Đợt này cập nhật báo cáo Markdown và slide, không chạy benchmark/demo/seed, không sửa dataset hoặc workbook. Bản Markdown trước được giữ tại `data/private/week10_dataset_clarification_20261116/before.md`.
