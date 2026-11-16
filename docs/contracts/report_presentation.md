# REPORT_PRESENTATION_V1 — diễn giải báo cáo thống nhất

Contract HTTP: trường `presentation` của `ReportRecord`, mô tả trong
[OpenAPI](../architecture/openapi.design.json) và
[JSON Schema](report_presentation.schema.json). Đây là lớp chỉ đọc, bên ngoài
`report.report_json`, không nằm trong hash C13 hoặc quyết định review C12.

Backend tạo cùng một projection cho FE và PDF/DOCX. JSON export giữ nguyên C13
để tiếp tục kiểm được hash. Không cập nhật DB chỉ vì thay cách trình bày.

## 1. Kết luận, phạm vi và độ phủ là ba thông tin khác nhau

| Trường | Ý nghĩa | Không được suy ra |
| --- | --- | --- |
| `raw_status` | Enum C07/C08 thật đã lưu | UNKNOWN luôn là thiếu dữ kiện |
| `display_status` | Kết hợp enum với disposition/exclusion đã lưu | Ngoài phạm vi đồng nghĩa không áp dụng luật hoặc đã tuân thủ |
| `coverage.finding_complete` | Đã nhận đủ kết quả criterion trong checklist | Đã đọc/xác minh toàn bộ tài liệu |
| `coverage.full_text_complete` | Cờ độ phủ bằng chứng toàn văn từ snapshot tổng hợp | Độ chính xác pháp lý hoặc human approval |
| `coverage.conclusion_complete` | Cờ tổng hợp `coverage_complete` gốc | Ghi đè kết luận COMPLIANT thành INSUFFICIENT |

Hai cờ đầu giữ `null` nếu báo cáo cũ chưa ghi riêng. Không chuyển giá trị chưa biết
thành false hoặc true. Đọc `coverage.explanation` để hiển thị cho người dùng.
Một kết luận nội dung có quote đủ căn cứ có thể tồn tại khi chưa chứng minh độ phủ
toàn văn. Ngược lại, kết luận **vắng nội dung** vẫn cần các gates xác nhận vắng
nội dung/đủ bộ tài liệu; không nới gates vì thay nhãn UI.

## 2. Mapping trạng thái

- C07 `excluded` với lý do `REVIEW_SCOPE_EXCLUDED:` → OUTSIDE_REVIEW_SCOPE.
- C07 `excluded` khác → EXCLUDED; C07 UNKNOWN không excluded vẫn UNKNOWN.
- C08 disposition OUTSIDE_REVIEW_SCOPE/NOT_TRIGGERED → hiển thị disposition đó.
- Các C08 khác giữ nguyên status. NEEDS_EVIDENCE vẫn là INSUFFICIENT.
- C05 NOT_APPLICABLE không có version → không chọn phiên bản vì không áp dụng.
- C05 chưa RESOLVED nhưng có version ID → phiên bản ứng viên, không phải đã xác nhận.

Rà soát dùng cùng display status như Tuân thủ, nhưng vẫn giữ giá trị máy gốc,
target ID, before/after, review hash và toàn bộ điều kiện publish. Không tự CONFIRM
các mục bị loại hoặc giảm số target phải review.

Diagnostic cũ `INSUFFICIENT_REQUIREMENT` được diễn giải thành
`REQUIREMENT_OUTSIDE_REVIEW_SCOPE` hoặc `REQUIREMENT_NOT_TRIGGERED` nếu có disposition
tương ứng. `raw_code` và danh sách diagnostic nguyên bản vẫn đọc được. Run mới sinh
đúng taxonomy ngay từ bước 5–7.

## 3. Khuyến nghị và template

Renderer bind biến có tên từ snapshot risk/finding, không dùng LLM để bịa thông tin.
Với citation chưa định danh, observed title là nguyên văn quan sát được, không phải
định danh phiên bản luật. `[nguyên văn]` bind quote hoặc observed title;
`[thông tin/bằng chứng cụ thể còn thiếu]` bind yêu cầu bổ sung cụ thể từ reason code
và lý do chưa xác minh, không chèn nguyên một câu giải thích vào vị trí tên tài liệu.

Template mới nên dùng `{quote}`, `{verification_request}`, `{uncertainty_reason}` và các tên trong
`resolved_bindings`. Các ô legacy chưa biết giá trị phải được ghi nhận, không in
một câu sửa chứa placeholder như thể đã hoàn thiện. Nếu thiếu dữ kiện để viết câu
sửa, giữ yêu cầu xác minh và nêu dữ kiện cần bổ sung. Template gốc luôn ở snapshot.

`presentation.recommendations` chỉ render lại slot của báo cáo legacy bằng dữ liệu
đã có trong cùng report. C11 mới có `rendering_policy=OBSERVED_TEMPLATE_BINDINGS_V1`
để không diễn giải lại dấu ngoặc nằm trong chính nguyên văn nguồn.

## 4. Ownership và nghiệm thu

- Người 4 sở hữu finding/disposition/gates, nguồn risk và bindings của C11.
- Người 5 sở hữu projection HTTP, cách hiển thị/review/export và tiến độ workflow.
- Người 1 quản lý release/schema, không cần sửa workbook để sửa nhãn.
- Người 2–3 tiếp tục cung cấp provenance và C05/C06 hợp lệ; không đổi field để chiều UI.

Nghiệm thu phải có cả trạng thái thực sự thiếu căn cứ lẫn mục ngoài phạm vi,
diện tích/đơn vị/phiên bản khác nhau, template thiếu bindings và nguồn xung đột.
Hash C13, JSON export và lịch sử C12 phải không đổi sau projection.

## 5. Diễn giải số liệu và audit

`FindingView.explanation` là diễn giải để hiển thị; `audit_trace` giữ dấu vết kỹ
thuật phục vụ đối chiếu. Hai trường phải đồng bộ giữa model backend, schema
presentation, OpenAPI và types frontend. Chúng không thay finding, evidence,
review hash hoặc nội dung C13 đã lưu.

- UNKNOWN và MISSING giữ ý nghĩa của chúng; không được suy thành đáp ứng.
- Không điền số liệu hoặc ngưỡng mặc định khi nguồn thiếu. Không gắn cứng ngưỡng
  bảo hành, tỷ lệ bảo trì hoặc đặt cọc trong lớp hiển thị.
- Số tiền và tỷ lệ là hai đại lượng khác nhau. Tỷ lệ trong rule dùng đơn vị phân
  số; chỉ đổi sang phần trăm khi trình bày, không đổi số tiền thành phần trăm.
- Output numeric mới nhận rule/facts trực tiếp. Bộ đọc audit legacy chỉ nhận
  JSON/Python data literals; không thực thi biểu thức. Nếu không đọc được, dùng
  diễn giải tổng quát theo finding đã lưu, không đoán số.
- Nếu số liệu đọc được mâu thuẫn trực tiếp với finding, thông báo cần rà soát;
  không viết lại finding của báo cáo lịch sử.
