# 09 — Async Workflow & Job Lifecycle

> **Tài liệu thẩm quyền liên quan:** [Kiến trúc hệ thống](../architecture/system_architecture.md) · [Kịch bản Demo](../guides/demo.md) · [Framework k3d / Argo CD](../devops/local_k3d_argocd_cicd_framework.md)  
> **Source code trung tâm:** [`assessments/service.py`](../../backend/src/legal_checker/modules/assessments/service.py) · [`assessments/runs.py`](../../backend/src/legal_checker/modules/assessments/runs.py) · [`workflows/runner.py`](../../backend/src/legal_checker/workflows/runner.py) · [`workflows/states.py`](../../backend/src/legal_checker/workflows/states.py) · [`worker/queues.py`](../../backend/src/legal_checker/worker/queues.py) · [`worker/tasks/analysis_tasks.py`](../../backend/src/legal_checker/worker/tasks/analysis_tasks.py)

---

## 1. Bài toán thực tế của một hệ thống đánh giá hợp đồng chạy nền

Một lượt chạy đánh giá toàn bộ hợp đồng (`C01` → `C11`) có thể mất từ vài giây (offline rule/BM25) đến vài phút (khi bật Hybrid Semantic + `FullDocumentReviewer` trên hợp đồng 80–166 trang). Không thể giữ một HTTP request `POST /runs` treo 3 phút chờ xong rồi mới trả về: trình duyệt sẽ timeout, người dùng bấm F5 hoặc click nút "Chạy đánh giá" 2 lần sẽ sinh ra 2 job trùng nhau, hoặc worker bị OOM giữa chừng khiến job kẹt mãi ở `RUNNING`.

Vì vậy, vòng đời của một Run được thiết kế theo mô hình **PostgreSQL là Source of Truth + Redis/Celery là Broker At-Least-Once**, vận hành qua 5 cơ chế tin cậy sau.

---

## 2. Vòng đời của một Run từ HTTP Request đến `COMPLETED`

```
Client (UI)                FastAPI                   PostgreSQL               Redis/Celery               Worker
    │                         │                           │                        │                       │
    ├─POST /cases/{id}/runs──►│                           │                        │                       │
    │ (Idempotency-Key: K1)   ├──1. Pin Knowledge/Deploy  │                        │                       │
    │                         ├──2. RunRepository.create ─► INSERT QUEUED          │                       │
    │                         │    (ON CONFLICT DO NOTHING)                        │                       │
    │                         ├──3. queue.enqueue ────────┼────────────────────────► push (ca_id, run_id) │
    │◄─202 RunAccepted────────┤                           │                        │                       │
    │                         │                           │                        ├─4. claim task ───────►│
    │                         │                           │◄─5. runs.claim(lease)──┤ (row lock + lease)    │
    │                         │                           │                        │  + start heartbeat()  │
    ├─SSE / Polling (sau F5)─►├─đọc trạng thái từ DB─────►│                        │                       │
    │                         │                           │◄─6. mark_stage(1..9)───┤  DraftWorkflow        │
    │                         │                           │                        │  .evaluate()          │
    │                         │                           │◄─7. ONE TRANSACTION:───┼─ Done! stop heartbeat │
    │                         │                           │   save_version(report) │                       │
    │                         │                           │   + runs.complete()    │                       │
```

### 2.1. `Idempotency-Key` chống click đúp & retry mạng (`RunRepository.create`)
Khi client gửi `POST /runs` kèm `Idempotency-Key`, `RunRepository.create()` thực thi `INSERT INTO runtime.workflow_runs ... ON CONFLICT (ca_id, idempotency_key) DO NOTHING`. Nếu mạng chập chờn khiến client hoặc gateway gửi lại cùng key đó, DB trả về **chính `RunRecord` cũ** thay vì đẻ thêm một run trùng lặp.

### 2.2. DB-First + Outbox Recovery: Redis rớt mạng cũng không mất job
Trong [`AssessmentService.start_run()`](../../backend/src/legal_checker/modules/assessments/service.py):
1. Hệ thống luôn **ghi dòng `QUEUED` vào PostgreSQL trước**, rồi mới gọi `self.queue.enqueue(ca_id, run_id)`.
2. Nếu API vừa insert `QUEUED` xong thì Redis mất kết nối hoặc pod API bị kill trước khi kịp `enqueue`: tác vụ định kỳ của **Celery Beat (`recover_runs`)** sẽ quét mọi dòng ở trạng thái `QUEUED` quá `run_requeue_after_seconds` mà chưa ai claim, rồi đưa lại vào hàng đợi.
3. Kể cả nếu Redis gửi trùng 1 message cho 2 worker cùng lúc (*at-least-once delivery*), hàm `runs.claim()` dùng row lock nên chỉ duy nhất **1 worker giành được quyền chạy**; worker còn lại nhận `None` và thoát êm đẹp.

### 2.3. Hai chế độ hàng đợi: `InlineQueue` vs `CeleryQueue` (`ASSESSMENT_QUEUE`)
Cả API và Worker đều gọi chung một use case `AssessmentRunner.execute()` (`workflows/runner.py`):
* **`ASSESSMENT_QUEUE=inline`:** Chạy trực tiếp đồng bộ/background trong tiến trình API. Lý tưởng cho local dev/debug không cần bật Redis & Celery.
* **`ASSESSMENT_QUEUE=celery`:** API đẩy `(ca_id, run_id)` (chỉ gửi IDs gọn nhẹ, không nhồi payload PDF lên Redis) sang Celery Worker chạy độc lập từ **cùng Docker image backend**.

---

## 3. Claim, Lease, Heartbeat & Khôi phục Worker chết

Điều gì xảy ra nếu Worker đang chạy đến Stage 6 (`RETRIEVAL`) trên hợp đồng 166 trang thì container bị Kubernetes OOMKill?

1. **Lease & Heartbeat (`analysis_tasks.py`):**
   * Khi `runner.execute()` claim được run, nó đặt thời hạn thuê (`lease = timedelta(minutes=10)` hoặc `settings.run_lease_seconds`) và kích hoạt callback `on_claim=thread.start`.
   * Luồng nền **`heartbeat()`** cứ mỗi `min(30s, lease / 3)` lại cập nhật timestamp giữ chỗ (`runs.heartbeat(ca_id, run_id)`).
   * Lưu ý thiết kế tinh tế trong code: `heartbeat` **chỉ được khởi chạy bên trong `on_claim` sau khi đã chiếm được lock**, đảm bảo một task trùng lặp không thể vô tình gia hạn lease hộ một worker cũ!
2. **Recovery khi Worker chết (`recover_runs`):**
   * Nếu worker chết đột ngột, `heartbeat()` ngừng đập. Sau khi quá hạn lease, Celery Beat gọi `AssessmentService.recover()` để thu hồi dòng `RUNNING` bị treo đó và đưa về `QUEUED` cho worker khỏe mạnh khác xử lý lại.
3. **Phân biệt Lỗi Tạm thời (`TransientRunError`) vs Lỗi Thật (`FAILED`):**
   * Trong `AssessmentRunner.execute()`: nếu gặp `TRANSIENT_ERRORS` (`psycopg.OperationalError`, `TimeoutError`, `ConnectionError`), runner gọi `runs.release()` trả run về `QUEUED` rồi ném `TransientRunError`. Task Celery được cấu hình **`autoretry_for=(TransientRunError,)`, `retry_backoff=5`, `retry_backoff_max=120`, `retry_jitter=True`, `max_retries=4`** để tự động thử lại có giãn cách ngẫu nhiên.
   * Mọi lỗi logic hoặc dữ liệu khác (`SourceMismatchError`, `ModulesUnavailable`, `ValueError` ở `handoffs.py`) đều ghi trạng thái `FAILED` kèm `failure_reason()` rõ ràng lên từng stage đang `RUNNING` (`on_stage`). **Ghi nhớ:** `FAILED` là trạng thái hạ tầng/quy trình, tuyệt đối không biến thành nhãn pháp lý.

---

## 4. Commit nguyên tử cuối Run & Tiến độ 9 Stages

* Trong lúc chạy `DraftAssessmentWorkflow.evaluate()`, mỗi chuyển pha của 9 stages (`INTAKE` → `DOCUMENT_INTELLIGENCE` → `SCOPE_RESOLUTION` → `TEMPORAL_RESOLUTION` → `CITATION_VALIDATION` → `RETRIEVAL` → `COMPLIANCE` → `RISK_AGGREGATION` → `RECOMMENDATION`) được `on_stage` ghi ngay vào `stages_json` trong DB để giao diện đọc qua SSE/polling (nếu user nhấn F5 trình duyệt, tiến độ không bị mất).
* Ở bước cuối của `AssessmentRunner.execute()`, hệ thống **mở một transaction PostgreSQL duy nhất** (`with connect_postgres(...) as connection:`) để thực hiện đồng thời:
  1. `self.reports.save_version(run_id, report, connection=connection)` (lưu `Report DRAFT` đầu tiên);
  2. `self.runs.complete(ca_id, run_id, draft, connection=connection)` (lưu `draft_json` + đổi `status = "COMPLETED"`).
* **Ý nghĩa:** Không bao giờ có chuyện `run.status == "COMPLETED"` mà client gọi API lấy báo cáo lại gặp 404 vì báo cáo chưa kịp ghi!

---

## 5. Đọc tiếp & Tham chiếu nhanh

* **Bước kế tiếp trong bộ Deep Dive:** [10 — Unknown, Insufficient & Diagnostics](10-unknown-insufficient-and-diagnostics.md)
* **Đối chiếu code:**
  * [`RunRepository`](../../backend/src/legal_checker/modules/assessments/runs.py) — SQL `ON CONFLICT` cho idempotency, `claim()`, `heartbeat()`, `release()`, `complete()`.
  * [`AssessmentRunner`](../../backend/src/legal_checker/workflows/runner.py) — điều phối claim → workflow → atomic report + complete, phân loại `TRANSIENT_ERRORS`.
  * [`analysis_tasks.py`](../../backend/src/legal_checker/worker/tasks/analysis_tasks.py) — luồng `heartbeat()` kích hoạt bởi `on_claim` và Celery Beat `recover_runs`.
