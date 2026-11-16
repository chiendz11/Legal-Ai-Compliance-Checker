# Demo E2E trên k3d và rà báo cáo — 09/11/2026

## 1. Phạm vi đã thực hiện

Đã upload PDF baseline v3 qua giao diện, tạo ca/run mới, chạy Celery worker với
modules và LLM thật, lưu report mới, mở tám tab và kiểm export/nguồn/lineage.
Không replay proposal, không dùng C02/C07 QA làm kết quả, không sửa kết luận của run.

| Mục | Giá trị |
| --- | --- |
| Case | `CA_UP_DFF9B41380DD` |
| Run | `RUN_235c39146bb44fa783db495b9bbd1914` |
| Report | `REPORT_ac376a8f-36a8-5f2c-bb0a-334c4eaa6533` |
| Report URL | [Mở báo cáo mới](http://app.legal-checker.localhost:18880/reports/REPORT_ac376a8f-36a8-5f2c-bb0a-334c4eaa6533?tab=compliance) |
| Chế độ | `DRAFT_REVIEW`, khai báo đủ bộ tài liệu trong phạm vi nội dung |
| Mốc intake | `TEMPLATE_USE`, 16/02/2017; giả định thời điểm rà dự thảo, không chứng nhận đã ký |
| PDF | `NEW_001BF40B2491_S01.pdf`, 78 trang, baseline v3 |
| Source SHA-256 | `9bac4ac8ae4a2e71584c8b421bce6106b3a3cec54061bfc678e869f2430b8e97` |
| Knowledge | `V750_RUNTIME_ALIGNMENT_20261108` |
| Knowledge SHA-256 | `32d59bcb9efe506389543bae5ee819d2d07d4a322425fa2d3ffa377c1eff698b` |
| Backend image | `legal-local/backend:image-6d6a99c0d929805798dd1f978527d72e1df0726f8c18fea41e846e23e981bc39` |
| Model | `gemini-3.5-flash-lite` |
| Kết thúc | `COMPLETED`, 18:33:11 ngày 09/11/2026, giờ Việt Nam |
| Thời gian | Khoảng 9 phút 48 giây, từ stage INTAKE tới COMPLETED |

Đây là nghiệm thu một ca tích hợp local, không phải nghiệm thu toàn corpus hoặc
xác nhận pháp lý do chuyên viên. Report vẫn DRAFT/PENDING; không tạo quyết định review.

## 2. Kết quả máy đã lưu

| Phần | Kết quả |
| --- | --- |
| Documents | 131 chunks, 56 facts, không có trang không đọc được |
| C05 | 323 yêu cầu xét; 75 CONFIRMED, 248 NOT_APPLICABLE, không có applicability UNKNOWN |
| C07 theo trạng thái hiển thị | 84 SATISFIED, 39 OUTSIDE_REVIEW_SCOPE, 6 EXCLUDED theo điều kiện |
| C08 theo trạng thái hiển thị | 59 COMPLIANT, 14 OUTSIDE_REVIEW_SCOPE, 2 NOT_TRIGGERED |
| C07/C08 thiếu căn cứ thực sự trong phạm vi đã xét | 0 |
| C09 | 10 VALID, 1 UNKNOWN |
| C10 | 0 risk tuân thủ, 0 risk viện dẫn đã xác lập, 1 risk cần xác minh |
| C11 | 1 VERIFY_REFERENCE cho viện dẫn chưa định danh |

14 yêu cầu ngoài phạm vi review không được tính là tuân thủ. Hai yêu cầu không
phát sinh điều kiện cũng không phải yêu cầu thiếu hồ sơ. Không gọi 59/75 là điểm
tuân thủ tổng hoặc kết luận toàn bộ hợp đồng hợp pháp.

C07 raw vẫn có 45 UNKNOWN vì các record bị loại trừ giữ enum gốc; toàn bộ 45 là
39 ngoài phạm vi và 6 loại theo điều kiện, không phải 45 criterion chưa được xử lý.
C08 raw vẫn có 16 INSUFFICIENT, nhưng disposition của chúng là 14 ngoài phạm vi
và 2 không phát sinh điều kiện. Summary UI/PDF/DOCX đã dùng disposition đúng.

### 2.1 Tiêu chí GTC

`TC_PV_HYC015_02` trong chính report mới là SATISFIED, model
`gemini-3.5-flash-lite`, prompt `C07_SEMANTIC_V13`, có nguồn trích dẫn và vẫn PENDING.
Không dùng lại recipe `DRAFT_INCORPORATED_RESIDENTIAL_RULES_V1` đã bỏ.

### 2.2 Một viện dẫn vẫn UNKNOWN

`HD_UP_DB027DA1DFB28FDF_VD_04025599616d_004` chỉ quan sát được tên
“Luật bảo vệ người tiêu dùng”, không có năm/số hiệu. C09 giữ
`NAME_ONLY_VERSION_IDENTITY_AMBIGUOUS`, không tự chọn phiên bản theo ngày ký.
C10 tạo VERIFICATION, C11 yêu cầu xác định nguồn/phiên bản; không khẳng định viện dẫn
sai và không dùng UNKNOWN này để làm thay đổi compliance của nhánh Applicable Law.

## 3. Các điểm bàn giao đã kiểm

25 kiểm tra trong `extended_inspection.json` đều pass, cùng các kiểm tra browser,
nguồn/export và artifact riêng:

- C01/context/source hash trùng report và run; C02/C03/C04/C05/C09 không lệch giữa
  snapshot đã chạy và nội dung FE đọc.
- C06 chỉ trỏ tới chunks hiện tại của extraction `04025599616d`; criterion thuộc
  đúng requirement version và run. Không mượn ID từ seed/reference cũ.
- Đã kiểm **285 quote C07** đúng lát text/offset trong chunk, cùng evidence của C02.
- C08 giữ đúng membership C07 và knowledge pin. Chạy lại phép tổng hợp thuần từ
  C05/C07 đã lưu cho kết quả bằng C08 đã lưu. Đây là kiểm nhất quán handoff, không
  phải đánh giá nhãn độc lập bằng cùng engine.
- C10 trỏ về C07/C09 có thật của run; C11 trỏ đúng risk và snapshot. Link trên UI
  Khuyến nghị → risk → viện dẫn hoạt động, nhóm risk xác minh tự mở khi focus.
- Full-document artifact đúng SHA-256/context/source; manifest hash khớp **131
  chunks**, đủ **55 criterion qua 4 batch nguồn**. Artifact loại MACHINE_FULL_TEXT,
  không giả làm chứng từ bên ngoài hoặc human review.
- F5 trang tiến độ vẫn đọc lại đúng run RUNNING; không tạo run mới hoặc làm mất job.
- 21 report trước đó giữ nguyên JSON/hash; report mới được lưu riêng.
- Kiểm tra contracts/tài liệu sau cập nhật: 37 test pass trong
  `test_integration_alignment.py` và `test_machine_contracts.py`;
  `git diff --check` không báo lỗi. Đây là kiểm tra bổ sung cho biên bản, không
  thay cho bằng chứng chạy thật và đối chiếu dữ liệu ở trên.

## 4. Kiểm tra tám tab và export

| Tab/chức năng | Kết quả quan sát |
| --- | --- |
| Hồ sơ | Hiển thị 56 facts; net area 62,4 m², gross area 67,4 m², bảo hành 60 tháng có dữ liệu; flags human review giữ riêng |
| Phạm vi | 323 xét/75 áp dụng/248 không áp dụng; các yêu cầu không chọn version do không áp dụng được giải thích riêng trên UI |
| Tuân thủ | 59 đạt, không có NON_COMPLIANT/PARTIAL hoặc thiếu căn cứ thực sự; 14 ngoài phạm vi và 2 không phát sinh điều kiện hiển thị riêng |
| Viện dẫn | 10 VALID/1 UNKNOWN; giữ raw title và mốc 2017; không điền định danh giả |
| Rủi ro | Một verification risk có nguồn C09; card đọc được khi mở nhóm hoặc theo link focus |
| Khuyến nghị | Một VERIFY_REFERENCE; link quay về risk và citation có thật |
| Rà soát | 0/217 mục được review; không auto-CONFIRM hoặc publish |
| Audit | Source/knowledge/run pin đúng, SOURCE_ONLY; có diagnostics và version hiện hành |
| Browser | Không ghi nhận JavaScript exception hoặc HTTP >=400 trong chuỗi kiểm tra |
| JSON | HTTP 200; payload export khớp report API |
| PDF | HTTP 200, 48 trang; tổng quan dùng disposition giống UI; file PDF hợp lệ |
| DOCX | HTTP 200; ZIP/document XML hợp lệ; tổng quan giống UI |
| PDF nguồn/split viewer | Tải được đúng PDF baseline v3, checksum khớp source của case |

## 5. Các điểm còn cần cải thiện, chưa sửa trong đợt chạy này

Không phát hiện lỗi chặn bàn giao dữ liệu trong các kiểm tra đã nêu. Vẫn có các
điểm về hiển thị, ngữ nghĩa và hiệu năng cần xử lý trước nghiệm thu rộng:

| Phát hiện | Bằng chứng và tác động | Owner phù hợp |
| --- | --- | --- |
| “Tuân thủ” kèm “chưa đủ độ phủ” | 27 C08 COMPLIANT có finding_coverage_complete=true nhưng evidence_coverage_complete=false. FE dùng một câu chung cho coverage_complete=false, dễ bị hiểu là thiếu criterion. Cần diễn giải riêng độ phủ checklist và độ phủ toàn văn, không tự bật gate để xóa nhãn | Người 4 và 5 |
| Rà soát còn dùng nhãn UNKNOWN cho mục ngoài phạm vi | Tab Tuân thủ đã hiển thị OUTSIDE_REVIEW_SCOPE nhưng danh sách review dùng finding gốc. Cần cùng một mapping hiển thị, giữ nguyên target/history/decision | Người 5 |
| Audit còn diagnostics INSUFFICIENT_REQUIREMENT cho disposition ngoài phạm vi | 16 diagnostic tương ứng 14 ngoài phạm vi và 2 không phát sinh điều kiện, không phải 16 thiếu căn cứ đang xét. Nên đổi taxonomy/cách nhóm hiển thị | Người 4 và 5 |
| Export chi tiết còn enum version UNKNOWN cho C05 NOT_APPLICABLE | Tổng quan PDF/DOCX đúng, nhưng bảng chi tiết vẫn in enum gốc thay cách giải thích “không chọn phiên bản vì không áp dụng” như UI | Người 5 |
| Khuyến nghị còn mẫu chưa điền | C11 đúng loại VERIFY_REFERENCE nhưng đoạn gợi ý vẫn có `[nguyên văn]`, `[thông tin/bằng chứng cụ thể còn thiếu]`; binding quote hiện rỗng dù C03 raw title có trong report. Cần bind dữ liệu quan sát được, không bịa luật thay thế | Người 4 và 5 |
| Progress chưa phản ánh đủ công việc đang chạy | Full-document LLM review chạy trong Retrieval, còn Citation Validation được gọi sau observations. UI vì vậy đứng lâu ở 4/9 hoặc 5/9 và citation vẫn PENDING. Không sai kết quả nhưng khó theo dõi | Người 5, phối hợp 3–4 |
| Chi phí/độ trễ | 50 HTTP attempts: 41 SUCCESS, 9 lỗi retry; khoảng 1.604.764 input và 24.015 output tokens. Cần giảm lặp context và đo budget theo token; không bỏ evidence hoặc giảm kiểm tra chỉ để chạy nhanh | Người 4 và 5 |

Tất cả lỗi provider ở attempts cuối cùng đã được phục hồi trong run này: diagnostics
kết quả không còn RATE_LIMIT/CALL_LIMIT/INVALID_MATRIX/FOREIGN_FACT_EVIDENCE gây
criterion chưa xử lý. Không xóa các lỗi tạm thời khỏi audit. Kết quả này chưa chứng
minh provider luôn ổn định hoặc mọi hợp đồng đều cho cùng chất lượng.

## 6. Artifact và giới hạn

Bằng chứng raw, screenshots, browser probes, audit counts và các kiểm tra nằm ngoài
Git tại `data/private/e2e_source_context_20261109/run_01/`.

Bản để người dùng mở/download được copy vào:

```text
/home/chienqt/Downloads/legal_checker_e2e_20261109/
```

Không đổi PDF, workbook, dataset manifest, seed DB hoặc business code trong đợt
này. Chỉ tạo một ca/run/report mới và đọc kết quả. Chưa thực hiện review/publish,
chưa chạy các biến thể thiếu/vi phạm/mâu thuẫn hoặc nghiệm thu Recall@K/accuracy trên
corpus. Các phần này vẫn cần kiểm chứng riêng trước khi phát hành dataset mới.
