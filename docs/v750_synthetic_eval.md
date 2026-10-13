# v7.5.0 Synthetic Evaluation — r2

Đây là bộ dữ liệu dành cho đồ án: 90 hồ sơ hư cấu có PDF tiếng Việt, text tương ứng,
profile, facts, input/output theo contracts và đáp án kiểm thử. Workbook gốc và bản r1
không bị ghi đè. Ngày seed cũ được giữ trong lịch sử; ngày kịch bản mới được chọn có chủ
đích trong năm 2024 để kiểm tra các mốc pháp luật đã đối chiếu, thay vì mặc nhiên áp dụng
các luật năm 2024 cho mọi ngày seed 2025–2026.

## Nhận đúng gói và seed DB

| Gói | Ca | Cách dùng |
|---|---:|---|
| SYNTHETIC_MASTER | 90 | Quản lý dữ liệu/evaluator, đủ nguồn và đáp án |
| SYNTHETIC_DEV_VALIDATION | 75 | Mỗi dev seed cùng bộ này vào DB local riêng |
| SYNTHETIC_TEST_INPUTS | 15 | Chỉ C01/PDF nguồn; chạy pipeline thật, evaluator giữ đáp án |

Mỗi nhóm tình huống có 6 ca: 4 DEV, 1 VALIDATION, 1 TEST. Tổng cộng 60/15/15.
Giữ split theo họ nguồn của r1, không đưa các bản của cùng hồ sơ qua nhiều split.
Các archetype pháp lý có mặt trong cả ba split; đây là kiểm tra kịch bản và biến thể,
không phải benchmark tổng quát hóa sang loại giao dịch hoàn toàn chưa thấy.
TEST không có assertions, C02–C13, PipelineRequest hoặc tên scenario tiết lộ đáp án.

Giải nén ZIP trong repo, ví dụ `data/private/v750_synthetic_r2/`, rồi dùng DB mới:

```bash
python -m scripts.local_db \
  --database-url 'postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_dev_v750_synthetic_r2' init
python -m scripts.local_db \
  --database-url 'postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_dev_v750_synthetic_r2' \
  seed --workbook data/private/v750_synthetic_r2/bang_du_lieu_runtime_v7_5_0_SYNTHETIC_DEV_VALIDATION.xlsx
```

Muốn API dùng DB này, đổi `DATABASE_URL` trong `.env`. DB cũ không bị thay dữ liệu.
`dataset://v750-synthetic-r2/sources/...` trỏ tới thư mục `sources/` trong gói đã giải nén;
đây là URI dataset để adapter lưu trữ ánh xạ, không phải URL tải qua HTTP.

## Các nhóm tình huống

| Nhóm | Điều kiện kịch bản | Hành vi cần kiểm tra |
|---|---|---|
| CLEAN_DOMESTIC | Chủ đầu tư trong nước, các khoản đúng ngưỡng | Nhánh SATISFIED/COMPLIANT |
| CLEAN_FOREIGN_BOUNDARY | Bên bán thuộc khoản 4 Điều 10, sát ngưỡng | So sánh bao gồm dấu bằng, ngưỡng 50% |
| FIRST_PAYMENT_EXCESS | Thu đợt đầu + cọc vượt 30% | VIOLATED/NON_COMPLIANT; không đếm cọc hai lần |
| FOREIGN_PREHANDOVER_EXCESS | Lũy kế trước bàn giao vượt 50% | Phân biệt bên bán trong nước/nước ngoài |
| PRE_CERTIFICATE_EXCESS | Chưa có GCN nhưng thu trên 95% | Rủi ro thanh toán có căn cứ |
| DEPOSIT_BREACH | Cọc trên 5%, chưa đủ điều kiện kinh doanh | Tách giới hạn cọc và điều kiện thu cọc |
| MAINTENANCE_WARRANTY_BREACH | Bảo trì 3%, bảo hành 36 tháng | Kiểm tra từng nghĩa vụ riêng |
| MISSING_CONTACT_PARTIAL | Có tên/địa chỉ, thiếu điện thoại | MISSING sau kiểm tra đủ; tổng hợp PARTIAL |
| MISSING_PROPERTY | Thiếu mô tả căn hộ trong hồ sơ đầy đủ | MISSING; yêu cầu một criterion có thể NON_COMPLIANT |
| ANNEX_NOT_RECEIVED | Phụ lục chưa nhận, chưa rõ mục đích mua | Scope/criterion UNKNOWN, không gán MISSING |
| CONFLICTING_PRICE | Hai giá khác nhau, chưa rõ bản ưu tiên | UNKNOWN cho các phép tính phụ thuộc giá |
| MISSING_RELEVANT_DATES | Thiếu ngày ký và ngày thu tiền | C05 UNKNOWN, C08 INSUFFICIENT |
| HISTORICAL_VALID | Mốc ký/thu và đánh giá trước 01/07/2024 | Chọn version cũ; viện dẫn có thể VALID tại mốc lịch sử |
| TRANSITION_UNRESOLVED | Ký trước 01/08, thu sau mốc này | Giữ UNKNOWN với nghĩa vụ chưa rõ chuyển tiếp |
| INDIVIDUAL_RESALE | Bán lại giữa cá nhân, không kinh doanh/chủ đầu tư | NO_MATCH/NOT_APPLICABLE cho các family đã chọn |

Phân phối thực tế nằm trong sheet `QA_COVERAGE` và `PHAN_PHOI.csv` của MASTER.
Không ép các nhãn theo tỷ lệ: kịch bản được thiết kế trước, nhãn theo predicates/rules,
rồi mới thống kê. Vì một hợp đồng có nhiều requirement, phần lớn requirement có thể
COMPLIANT dù hợp đồng chứa một nghĩa vụ VIOLATED. Không có nhãn COMPLIANT toàn hợp đồng.
Khi chấm C07/C08, báo cáo từng lớp và macro-F1; không chỉ accuracy chung vì nhiều điều
khoản đúng có thể che việc bỏ sót một vi phạm. `SELECTED_CHECKLIST_BRANCH` chỉ tóm tắt
nhánh của checklist đã chọn, không phải kết luận pháp lý đầy đủ cho toàn hợp đồng.

## Các quy tắc pháp lý và giả định

Scope dựa vào loại tài sản, kinh doanh hay bán lại, chủ đầu tư, mục đích mua và hợp đồng
theo mẫu. Temporal dùng khoảng hiệu lực `[từ, đến)`: điều khoản dùng ngày ký; đặt cọc và
thu tiền dùng mốc thu tương ứng. Chuyển tiếp chưa xác định không tự trở thành CONFIRMED.
Enum thật của C05 là `MATCH/RESOLVED/CONFIRMED`, không có `APPLICABLE`.

Các kịch bản hiện đại xét các giới hạn thanh toán và đặt cọc trong scope căn hộ thương mại
hình thành trong tương lai; nội dung hợp đồng theo Điều 46 cũng được xét. Căn cứ giới hạn
và mốc hiệu lực: [Luật 29/2023/QH15, Điều 23, 25, 46](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/01/luat29.pdf)
và [Luật 43/2024/QH15, Điều 3](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/9/43-2024-qh15.pdf).
Thông tin các bên/đối tượng trong hợp đồng theo mẫu dựa vào
[Luật 19/2023/QH15, Điều 3, 23](https://datafiles.chinhphu.vn/cpp/files/vbpq/2023/7/luat19_2023.pdf).
Bảo trì và bảo hành trong scope đã khai báo dựa vào
[Luật 27/2023/QH15, Điều 129, 152](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/01/luat27_tiep.pdf).
Phiên bản lịch sử tham chiếu
[Luật 66/2014/QH13](https://datafiles.chinhphu.vn/cpp/files/vbpq/2014/12/66.signed.pdf)
và knowledge lịch sử hiện có. Cọc trong kịch bản lịch sử bằng 0 để không tự phân giải
cách tính cọc còn cần xem xét; cơ sở tính bảo trì lịch sử là giả định được khai báo rõ.

Chỉ xét **9 requirement families**, không bao phủ toàn bộ nghĩa vụ pháp lý của hợp đồng.
Riêng bán lại giữa cá nhân cần checklist khác; NOT_APPLICABLE không có nghĩa hợp đồng đó
đã tuân thủ mọi luật. Với nhánh lịch sử, hai family bổ sung chỉ tồn tại năm 2024 không
được áp ngược thời gian; không suy rằng luật cũ không có nghĩa vụ tương tự.

Knowledge pháp luật và hash gốc được giữ nguyên. Gates true trong kịch bản có đủ nguồn
nghĩa là đã đủ trong **vũ trụ kiểm thử được khai báo**, không phải đã có chuyên gia duyệt.
Mọi `human_verified=false`, recommendation `PENDING`, report `DRAFT`.
Severity giữ theo catalog hiện tại; không gán mức nghiêm trọng để làm đẹp phân phối.

## Phát triển và kiểm tra từng module

Các module query bảng nghiệp vụ để dựng DTO. `qa.artifacts` lưu snapshots theo contract;
`qa.controlled_assertions` lưu đáp án dựa trên kịch bản được viết trước khi chạy engine.
Không có bảng nghiệp vụ mới. Sáu bảng QA của r1 được dùng lại.

1. **Bước 1–2:** đọc PDF synthetic thật; so profile/facts/citation với C02/C03 và
   `DocumentIntelligenceResult`. PDF có text tiếng Việt; bộ này chưa đo OCR trên scan.
   Chuẩn hóa whitespace khi so text; không buộc module sinh đúng IDs/chunking của reference.
2. **Bước 3:** dùng profile và knowledge để tự viết Scope/Temporal/Citation Validator.
   So C04/C05/C09 với reference; phân biệt date sự kiện, phiên bản, domain và identity.
   Reference resolver trong devtools chỉ hỗ trợ 9 family; service production vẫn cần làm.
3. **Bước 4:** nhận C05 + chunks + criteria; tự tìm evidence. C06 seed là relevance oracle,
   không phải output của retriever đã hoàn thiện. Các candidates có cả đoạn liên quan và
   đoạn không liên quan. `embedding_json` chỉ là lexical index mẫu, không phải dense vector.
4. **Bước 5–7:** dùng C06 và C09 mẫu để chạy logic hiện tại hoặc phát triển LLM adapter;
   kiểm tra C07/C08/C10/C11. Không đọc đáp án của chính module để trả output.
5. **Bước 9:** dùng C13 draft để phát triển hiển thị/report; giữ nguồn criterion/citation
   của risk riêng. Review/auth/publish cần triển khai thật, không dùng dữ liệu để giả duyệt.

```sql
SELECT case_id, split, limitations_json->>'scenario' AS scenario
FROM qa.case_manifest ORDER BY case_id;

SELECT * FROM qa.controlled_assertions WHERE case_id = 'CA90_001';

-- Đọc một C05; thực tế repository phải lọc thêm lần chạy/version theo contract.
SELECT * FROM runtime.yeu_cau_ap_dung WHERE ca_id = 'CA90_001';
```

Chạy kiểm tra từ DB local và chạy mới cho một ca DEV:

```bash
python -m scripts.eval_local_db --database-url "$DATABASE_URL" --split DEV
python -m scripts.eval_local_db --database-url "$DATABASE_URL" --split VALIDATION
python -m scripts.run_case_from_db --database-url "$DATABASE_URL" \
  --case CA90_001 --run SYN_DEV_001
```

Chọn case thuộc DEV/VALIDATION trên máy mình; runner chặn TEST và run ID tham chiếu.
CLI eval hiện chạy engine **5–7**: so assertions độc lập và reference snapshots, không
đánh giá chất lượng module 1–4 hoặc LLM chưa triển khai. C09 ở đây là input chuẩn của Risk.
Muốn E2E phải chạy PDF qua các implementation thật, giữ TEST chưa dùng để chỉnh prompt.

## Tái tạo bộ dữ liệu

```bash
python -m scripts.synthetic_workbook \
  --input /path/bang_du_lieu_runtime_v7_5_0_90_ca_danh_gia_SILVER.xlsx \
  --split-from /path/bang_du_lieu_runtime_v7_5_0_DEV_EVAL_MASTER.xlsx \
  --legal-checks /path/legal_checks.json \
  --font-path /usr/share/fonts/noto/NotoSans-Regular.ttf \
  --output-dir data/private/v750_synthetic_r2
```

Đáp án được validate bằng Pydantic contracts; PK/FK/ownership và multipart SHA được
kiểm tra; workbook đọc lại sau xuất. Không ghi workbook/source/TEST labels lên repo public.
Script tái tạo có thể chạy từ dữ liệu private; mọi thành viên chỉ cần ZIP DEV để seed.
