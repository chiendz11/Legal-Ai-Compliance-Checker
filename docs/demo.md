# Kịch bản demo: từ ca đánh giá tới báo cáo C13

Demo đi qua luồng thật của nhóm D: API → hàng đợi → runner → `DraftAssessmentWorkflow` →
`build_draft_report` → lưu phiên bản → UI → export. Khi các module bước 1–7 chưa có, bật
`ASSESSMENT_MODULES=reference` để **phát lại tham chiếu QA**. Kết quả là dữ liệu tham chiếu,
không phải output của module; UI và file export đều ghi rõ `REFERENCE_REPLAY`.

## 1. Chuẩn bị (một lần)

Làm theo [dev_setup.md](dev_setup.md) tới khi DB đã seed, rồi cập nhật schema mới:

```bash
python -m scripts.local_db init
```

Trong `.env` của bạn:

```bash
ASSESSMENT_MODULES=reference
ASSESSMENT_QUEUE=inline
```

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

1. **Danh sách ca**: 300 ca DEV/VALIDATION. Thanh trên hiện "Backend online".
2. Bấm **Chạy đánh giá** ở `CA360_051`. Trang run hiện 9 stage chuyển PENDING → RUNNING →
   COMPLETED. Nói rõ: COMPLETED là có kết quả máy, chưa phải đã review.
3. Trang tự mở **báo cáo**. Chỉ vào hai nhãn: DRAFT/chưa review và REFERENCE_REPLAY.
4. Ô tổng hợp: chỉ đếm theo trạng thái, **không có điểm tổng**; UNKNOWN/INSUFFICIENT vẫn hiện.
5. Tab **Tuân thủ**: mở yêu cầu "Không tuân thủ" → tiêu chí "Vi phạm" → trích dẫn hợp đồng
   (đoạn, vị trí ký tự) và căn cứ. Bấm link rủi ro → nhảy sang tab **Rủi ro** đúng mục;
   bấm "Tiêu chí…" để quay lại (trả lời câu hỏi "rủi ro đến từ compliance hay citation").
6. Tab **Viện dẫn**: trạng thái tại ngày liên quan và trạng thái hiện tại tách riêng.
7. Tab **Audit**: run ID, snapshot tri thức, rule version để tái hiện.
8. **Tải PDF/DOCX**: file giữ nhãn DRAFT và REFERENCE_REPLAY, mã báo cáo trong tên file.
9. Bấm chạy lại cùng ca: tạo run mới; gửi lại cùng `Idempotency-Key` trả đúng run cũ.

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

- Chưa có module thật bước 1–7: reference replay chỉ chứng minh điều phối, lưu trữ, báo cáo, UI.
- Chưa có review (C12): mọi báo cáo là DRAFT/PENDING; publish chưa triển khai.
- Chưa có xác thực và phân quyền tenant.
- Báo cáo lưu ở `runtime.report_versions`; bảng workbook `bao_cao_danh_gia` chưa được ghi vì
  `phien_ban_bao_cao` INTEGER vs chuỗi `draft-v1` cần nhóm thống nhất cách ánh xạ.
