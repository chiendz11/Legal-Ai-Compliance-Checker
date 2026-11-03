# Kịch bản demo: từ ca đánh giá tới báo cáo C13

Demo đi qua luồng thật của nhóm D: tải hợp đồng → API → hàng đợi → runner →
`DraftAssessmentWorkflow` → báo cáo C13 → rà soát (C12) → phát hành → export có dấu xác thực.

Chọn nguồn module bằng `ASSESSMENT_MODULES`:

- `modules`: module thật của cả ba nhóm. Hợp đồng có tệp gốc trên máy chủ (tải lên qua UI, hoặc
  PDF đã nạp vào cache bằng `python -m scripts.seed_source_cache <thư mục PDF>`) được đọc bằng
  module nhóm A, báo cáo ghi `MODULES`. Ca dataset chỉ có PDF trên máy chủ lưu trữ ngoài thì
  bước 1–2 lấy từ dataset tham chiếu, báo cáo ghi `MODULES_DI_REFERENCE`. Với
  `ASSESSMENT_LLM=offline` (mặc định) tiêu chí C07 là UNKNOWN.
- `reference`: **phát lại tham chiếu QA** qua luồng điều phối thật; báo cáo ghi `REFERENCE_REPLAY`.
- `none`: run thất bại với `MODULE_NOT_IMPLEMENTED` (minh họa xử lý lỗi).

## 1. Chuẩn bị (một lần)

Làm theo [dev_setup.md](dev_setup.md) tới khi DB đã seed, rồi cập nhật schema mới:

```bash
python -m scripts.local_db init
```

Trong `.env` của bạn:

```bash
ASSESSMENT_MODULES=modules
ASSESSMENT_QUEUE=inline
ASSESSMENT_LLM=offline
```

Muốn demo phân quyền: đặt `AUTH_MODE=on`, `AUTH_SECRET=<≥32 ký tự ngẫu nhiên>` và tạo tài
khoản (mật khẩu nhập ẩn):

```bash
python -m scripts.users add reviewer1 --tenant LOCAL_SOURCE_PDF360 --name "Chuyên viên A" --roles viewer,reviewer
```

```bash
python -m scripts.users add lead1 --tenant LOCAL_SOURCE_PDF360 --name "Trưởng nhóm" --roles viewer,uploader,reviewer,publisher
```

Để `AUTH_MODE=off` thì mọi request chạy bằng tài khoản dev đủ quyền.

## 2. Chạy local (không cần Docker/Redis)

```bash
python -m uvicorn legal_checker.main:create_app --factory --host 127.0.0.1 --port 8000
```

```bash
npm --prefix frontend install
```

```bash
npm --prefix frontend run dev
```

Mở http://localhost:5173. Windows: nếu test/seed báo lỗi giải mã ký tự, đặt `PYTHONUTF8=1`.

## 3. Kịch bản trình bày (~5 phút)

1. (AUTH_MODE=on) **Đăng nhập** bằng tài khoản trưởng nhóm; góc phải hiện tên và vai trò.
2. **Lịch sử**: 300 ca DEV/VALIDATION; lọc theo trạng thái run/kết luận, tìm theo mã, sắp xếp.
3. **Tải hợp đồng**: kéo thả một PDF có lớp chữ → tạo ca → chạy. Cả 9 bước chạy bằng module
   thật và báo cáo ghi `MODULES`. Tải DOCX thì run dừng ở bước đọc hợp đồng với lý do
   `DOCUMENT_FORMAT_UNSUPPORTED` (nhóm A chưa có parser DOCX).
4. Bấm **Chạy đánh giá** ở `CA360_051`. Trang run hiện 9 stage chuyển PENDING → RUNNING →
   COMPLETED (cập nhật qua SSE). Nói rõ: COMPLETED là có kết quả máy, chưa phải đã review.
5. Trang tự mở **báo cáo**. Chỉ vào nhãn DRAFT/chưa review và nhãn nguồn module.
   Bấm **Xem song song với hợp đồng** để mở PDF gốc cạnh báo cáo; bấm trích dẫn → nhảy trang.
4. Ô tổng hợp: chỉ đếm theo trạng thái, **không có điểm tổng**; UNKNOWN/INSUFFICIENT vẫn hiện.
5. Tab **Tuân thủ**: mở yêu cầu "Không tuân thủ" → tiêu chí "Vi phạm" → trích dẫn hợp đồng
   (đoạn, vị trí ký tự) và căn cứ. Bấm link rủi ro → nhảy sang tab **Rủi ro** đúng mục;
   bấm "Tiêu chí…" để quay lại (trả lời câu hỏi "rủi ro đến từ compliance hay citation").
6. Tab **Viện dẫn**: trạng thái tại ngày liên quan và trạng thái hiện tại tách riêng.
7. Tab **Rà soát**: mỗi kết quả máy có nút review. Xác nhận một tiêu chí, chỉnh sửa mức độ một
   rủi ro (bắt buộc ghi lý do). Thử sửa sai contract (vd. đổi tiêu chí sang "Đáp ứng" khi không
   có bằng chứng) → server từ chối. Hai người cùng sửa một mục → người sau nhận `STALE_REVIEW`
   và trạng thái tự tải lại.
8. **Tạo phiên bản báo cáo từ review** → phiên bản mới (IN_REVIEW). Nếu còn mục chặn (yêu cầu bổ
   sung, rủi ro cao chưa xác nhận...) nút **Phát hành** bị khóa; xử lý xong thì phát hành →
   phiên bản PUBLISHED/APPROVED mới, bản cũ giữ nguyên.
9. Tab **Audit**: run ID, snapshot tri thức, rule version, lịch sử review (C12), thông tin phát hành.
10. **Tải PDF/DOCX/JSON**: cuối file có bảng **Dấu xác thực** (SHA-256 báo cáo, run, review
    revision, phiên bản tri thức, người/giờ xuất). File JSON chứa đúng đối tượng báo cáo đã lưu:
    tính lại SHA-256 sẽ khớp `report_sha256`.
11. Bấm chạy lại cùng ca: tạo run mới; gửi lại cùng `Idempotency-Key` trả đúng run cũ.

Lỗi minh họa: đặt `ASSESSMENT_MODULES=none`, khởi động lại API, chạy một ca → run FAILED với
`MODULE_NOT_IMPLEMENTED`, không có báo cáo nào bị tạo.

## 4. Kiểm tra bằng API (tùy chọn)

```bash
curl -s -X POST -H "Idempotency-Key: demo-1" http://127.0.0.1:8000/api/v1/cases/CA360_051/runs
```

Dùng `status_url` trả về để xem tiến độ; khi COMPLETED gọi
`/api/v1/cases/CA360_051/runs/<run_id>/reports`.

## 5. Docker Compose (khi máy có Docker)

DB vẫn migrate/seed từ host như bước 1 (dataset nằm ngoài image). Sau đó:

```bash
ASSESSMENT_MODULES=reference docker compose --profile app up -d --build
```

UI tại http://127.0.0.1:8080, API tại http://127.0.0.1:8000. Stack gồm postgres, redis,
api (`ASSESSMENT_QUEUE=celery`), worker (Celery + beat khôi phục run bị mất) và frontend (nginx).

## Giới hạn hiện tại

- Module đọc hợp đồng (nhóm A) chỉ đọc PDF có lớp chữ: chưa có OCR cho bản scan và chưa đọc DOCX.
- Ca dataset có sẵn dùng hồ sơ/đoạn văn tham chiếu khi PDF gốc không có trên máy chủ.
- C09 có chẩn đoán `C09_PROVENANCE_UNAVAILABLE` (khoảng trống tích hợp nhóm B/C).
- PDF gốc của các ca seed nằm trên host lưu trữ của dataset; khi host đó không truy cập được,
  khung xem song song báo lỗi rõ ràng (báo cáo vẫn dùng được). Hợp đồng tải lên thì xem được.
- Tài khoản quản lý bằng CLI `scripts.users`, chưa có màn hình quản trị.
- Báo cáo lưu ở `runtime.report_versions`; bảng workbook `bao_cao_danh_gia` chưa được ghi vì
  `phien_ban_bao_cao` INTEGER vs chuỗi `draft-v1` cần nhóm thống nhất cách ánh xạ.
