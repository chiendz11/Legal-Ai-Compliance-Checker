# 08 — Report Generation (`C13`) & Human Review (`C12`)

> **Tài liệu thẩm quyền liên quan:** [Nhóm D — Report & Frontend](../modules/group_d_report_and_frontend.md) · [Report Presentation](../contracts/report_presentation.md) · [Draft Review Policy](../contracts/draft_review_policy.json)  
> **Source code trung tâm:** [`reviews/service.py`](../../backend/src/legal_checker/modules/reviews/service.py) · [`assessments/service.py`](../../backend/src/legal_checker/modules/assessments/service.py) · [`reports/builder.py`](../../backend/src/legal_checker/modules/reports/builder.py) · [`reports/presentation.py`](../../backend/src/legal_checker/modules/reports/presentation.py) · [`reports/exporter.py`](../../backend/src/legal_checker/modules/reports/exporter.py) · [`ReportPage.tsx`](../../frontend/src/features/reports/ReportPage.tsx)

---

## 0. Trình bày nhanh (đọc phần này trước khi thuyết trình)

> **Một câu:** Người duyệt không sửa đè kết quả của máy: mỗi thao tác là một sự kiện ghi thêm, trạng thái hiện hành được tính bằng cách phủ sự kiện lên kết quả gốc, và báo cáo chỉ phát hành khi mọi mục đã được xác nhận hoặc sửa hợp lệ.

**Hình dung đời thường.** Giống chấm bài có bút đỏ: bài làm của học sinh (kết quả máy) không bị tẩy xoá; giáo viên ghi nhận xét và điểm sửa bên lề, có ký tên và lý do. Bảng điểm cuối cùng là bài gốc cộng các nhận xét. Hai giáo viên không thể cùng sửa một câu mà không biết người kia vừa sửa. Và mọi bản in đều ghi rõ “bản nháp” cho tới khi chấm xong.

**Ba ý phải nói được:**

1. **Ba cơ chế bất biến:** nhật ký sự kiện chỉ ghi thêm (C12) · lớp hiệu lực · mỗi lần sinh báo cáo là một phiên bản mới.
2. **Khoá lạc quan `expected_target_sha256`:** thao tác trên trạng thái cũ bị từ chối (409) và phải tải lại.
3. **Một phép chiếu duy nhất `ReportPresentation`:** web và file xuất PDF/DOCX/JSON luôn giống nhau; file xuất có dấu xác thực SHA-256.

**Thuật ngữ dùng trong chương:**

| Thuật ngữ | Nghĩa dễ hiểu |
|---|---|
| `CONFIRM` / `OVERRIDE` | Xác nhận / sửa kết quả của máy (hai quyết định “chốt”). |
| `REQUEST_MORE_EVIDENCE` / `REJECT` | Hai quyết định chặn phát hành. |
| Effective layer | Trạng thái hiện hành = kết quả máy + các sửa đổi của người. |
| Publish gate | Điều kiện phát hành: mọi mục có `CONFIRM` hoặc `OVERRIDE` hợp lệ. |
| `verification_stamp` | Dấu xác thực trên file xuất (mã báo cáo, run, review, SHA-256). |

**Slide tương ứng:** 34–35 trong [deck Công nghệ C01–C13](../business/slides/cong_nghe_va_ky_thuat_he_thong_c01_c13.pptx) · **Thời lượng gợi ý:** 4–5 phút.

---

## 1. Tại sao Human Review (`C12`) KHÔNG BAO GIỜ ghi đè trực tiếp dữ liệu AI?

Nếu một hệ thống cho phép reviewer bấm "Sửa kết luận từ `VIOLATED` thành `SATISFIED`" bằng cách chạy `UPDATE workflow_runs SET draft_json = ...`, hàng loạt rủi ro kiểm toán sẽ xảy ra:
* Không còn phân biệt được **phán đoán ban đầu của máy** với **quyết định của con người** (mất dấu AI provenance khi đánh giá chất lượng mô hình hoặc thanh tra nội bộ).
* Hai reviewer cùng mở một finding ở 2 tab và bấm lưu đồng thời sẽ âm thầm ghi đè công sức của nhau (**lost update**).
* Nếu một finding đã được duyệt hôm qua, làm sao biết hôm nay bảng báo cáo xuất ra PDF có đang phản ánh đúng bản review đó hay không?

Vì vậy, kiến trúc `C12/C13` được xây quanh **3 cơ chế bất biến**:
1. **Append-only Event Log (`HumanReview`):** Mỗi thao tác của reviewer được ghi thành một sự kiện mới (`CONFIRM`, `OVERRIDE`, `REQUEST_MORE_EVIDENCE`, `REJECT`, `COMMENT`) gắn kèm `actor`, `reason`, `before`, `after`, `target_sha256`. `workflow_runs.draft_json` của máy giữ nguyên vĩnh viễn.
2. **Effective Layer (Lớp phủ hiệu lực):** Hàm `target_states()` phát lại danh sách `events` lên trên `machine_targets(draft)` để tính ra `TargetState.effective` (`{**self.machine, **self.overrides}`) và tổng hợp `review_layer()` cho báo cáo.
3. **Immutable Report Versioning (`report_versions`):** Mỗi khi sinh báo cáo sau review hoặc phát hành, hệ thống tạo một **`bao_cao_id` mới** theo `review_revision` — không bao giờ ghi đè phiên bản báo cáo cũ.

---

## 2. Cơ chế hoạt động chi tiết của `C12` Review Service (`reviews/service.py`)

### 2.1. Năm loại đối tượng được phép review (`TARGETS`) & Giới hạn `OVERRIDE`

Reviewer không thể sửa bừa mọi trường JSON (ví dụ không được tự bịa `knowledge_snapshot_sha256` hay đổi `finding_id`). Bảng `TARGETS` khóa cứng chính xác **5 đối tượng và các trường được phép `OVERRIDE`**:

| `doi_tuong_loai` | Nguồn gốc trong `AssessmentDraft` | Khóa định danh | Trường được phép sửa khi `OVERRIDE` |
|---|---|---|---|
| `ket_qua_tieu_chi` (`C07`) | `evaluation.payload.criterion_results` | `ket_qua_id` | `finding`, `giai_thich` |
| `ket_qua_tuan_thu` (`C08`) | `evaluation.payload.requirement_results` | `tuan_thu_id` | `status` |
| `phat_hien_vien_dan` (`C09`) | `draft.citation_findings` | `finding_id` | `status`, `ly_do` |
| `ket_qua_rui_ro` (`C10`) | `evaluation.payload.risks` | `ket_qua_rui_ro_id` | `severity`, `giai_thich` |
| `khuyen_nghi_danh_gia` (`C11`) | `evaluation.payload.recommendations` | `khuyen_nghi_ca_id` | `noi_dung`, `uu_tien` |

Mọi lệnh `OVERRIDE` đều bị [`check_review()`](../../backend/src/legal_checker/modules/reviews/service.py) ép chạy lại Pydantic validator `kind.model.model_validate({**state.effective, **after})` (nếu đặt giá trị sai enum lập tức bị từ chối) và cấm `OVERRIDE` y hệt giá trị cũ (bắt buộc dùng `CONFIRM`).

### 2.2. Khóa lạc quan `expected_target_sha256` chống xung đột đồng thời

```
Reviewer A mở màn hình ──► Nhận target + target.sha256 = "a1b2c3..."
Reviewer B mở màn hình ──► Nhận target + target.sha256 = "a1b2c3..."

1. Reviewer A bấm OVERRIDE trước (kèm expected_target_sha256 = "a1b2c3...")
   ──► Thành công! `TargetState.effective` thay đổi → `state.sha256` đổi sang "f9e8d7..."
2. Reviewer B bấm CONFIRM (gửi kèm expected_target_sha256 = "a1b2c3...")
   ──► Backend giữ per-run lock, kiểm thấy `state.sha256 ("f9e8d7...") != "a1b2c3..."`
   ──► Ném `StaleReview` (HTTP Conflict 409): buộc Reviewer B tải lại trạng thái mới trước khi duyệt!
```

### 2.3. Publish Gate (`publication_blockers`)

Một run đạt `COMPLETED` mới chỉ có **Báo cáo Nháp (`DRAFT`)**. Để phát hành báo cáo chính thức (`publish_report`), hàm `publication_blockers()` quét toàn bộ `TargetState`:
* Nếu bất kỳ target nào có `latest_decision` thuộc **`BLOCKING` (`REQUEST_MORE_EVIDENCE`, `REJECT`)** → Chặn phát hành (`ReviewRequired`).
* Nếu bất kỳ target nào chưa có quyết định chốt (`latest_decision not in ("CONFIRM", "OVERRIDE")`, ví dụ chỉ mới có `COMMENT` hoặc chưa ai xem `UNREVIEWED_FINDING`) → Chặn phát hành!
* Chỉ khi tất cả target có `CONFIRM` hoặc `OVERRIDE` hợp lệ, bản report phát hành mới chuyển trạng thái và ghi nhận `review_revision` (ví dụ `r14-3a91c0...`).

---

## 3. Single Projection (`ReportPresentation`) & Export có Dấu Xác Thực

### 3.1. Tại sao UI React và Exporter PDF/DOCX/JSON dùng chung `build_presentation()`?

Trước đây, nếu Frontend tự viết logic hiển thị tiếng Việt, tự lọc bỏ chuỗi JSON/mã debug trong khuyến nghị, rồi Backend Export PDF lại viết một hàm format khác, người dùng sẽ thấy **trên web một kiểu, xuất PDF ra một nẻo**.

Do đó, [`presentation.py`](../../backend/src/legal_checker/modules/reports/presentation.py) và [`assessment_status.py`](../../backend/src/legal_checker/modules/reports/assessment_status.py) cung cấp một **Single Projection (`ReportPresentation`)**:
* UI React (`ReportPage.tsx` qua `ReportPresentationContext`) chỉ đọc `record.presentation` (chứa `CoverageView`, `FindingView`, `RecommendationView`, không tự `JOIN` DB hay sửa nhãn pháp lý).
* Bộ [`exporter.py`](../../backend/src/legal_checker/modules/reports/exporter.py) dùng đúng `build_presentation()` và `requirement_display_status` / `criterion_display_status` để dựng `Document` AST (headings, paragraphs, tables, quotes) rồi xuất ra PDF, DOCX hoặc JSON.

### 3.2. Dấu xác thực xuất bản (`verification_stamp`)

Mọi file PDF/DOCX/JSON được export đều gắn kèm `verification_stamp` (`lc-export-stamp/1`) gồm:
* `bao_cao_id`, `phien_ban_bao_cao`, `report_status` (`DRAFT` hay `PUBLISHED`), `review_status`;
* `ca_id`, `run_id`, `review_revision`;
* `report_sha256` (băm SHA-256 trên JSON chuẩn hóa của báo cáo), `exported_at`, `exported_by`.

Đặc biệt, nếu báo cáo chưa phát hành chính thức (`DRAFT` / còn mục `PENDING`), mọi trang/đầu file xuất ra **bắt buộc hiển thị dấu cảnh báo bản nháp chưa phê duyệt**, ngăn tuyệt đối việc lấy file nháp của AI đem trình ký như bản thẩm định cuối cùng.

---

## Hỏi – đáp khi trình bày

**Hỏi: Người duyệt sửa kết luận thì có mất dấu kết luận ban đầu của máy không?**  
Đáp: Không. `draft_json` giữ nguyên; sự kiện `OVERRIDE` lưu `before`, `after`, người sửa và lý do. Nhờ đó vẫn đánh giá được chất lượng máy và truy được trách nhiệm.

**Hỏi: Người duyệt có sửa được mọi thứ không?**  
Đáp: Không. Chỉ 5 loại đối tượng và một số trường nhất định (ví dụ `finding` và `giai_thich` của C07); giá trị mới phải qua validator Pydantic.

**Hỏi: Có thể xuất báo cáo khi chưa duyệt xong không?**  
Đáp: Xuất được, nhưng file bắt buộc mang dấu bản nháp chưa phê duyệt.

**Hiểu lầm hay gặp cần tránh khi nói:**

* `COMMENT` không phải là quyết định chốt — mục chỉ có bình luận vẫn chặn phát hành.
* UI không tự tính nhãn pháp lý; mọi nhãn hiển thị đến từ `ReportPresentation`.

---

## 4. Đọc tiếp & Tham chiếu nhanh

* **Bước kế tiếp trong bộ Deep Dive:** [09 — Async Workflow & Job Lifecycle](09-async-workflow-and-job-lifecycle.md)
* **Đối chiếu code:**
  * [`reviews/service.py`](../../backend/src/legal_checker/modules/reviews/service.py) — `TargetState`, `check_review`, `StaleReview`, `publication_blockers`, `review_revision`.
  * [`AssessmentService.build_report()`](../../backend/src/legal_checker/modules/assessments/service.py) — tạo version mới theo `review_revision` mà không sửa output máy.
  * [`exporter.py`](../../backend/src/legal_checker/modules/reports/exporter.py) — `verification_stamp()` và dựng export PDF/DOCX/JSON.
  * [`ReportPage.tsx`](../../frontend/src/features/reports/ReportPage.tsx) — hiển thị 8 khu vực báo cáo, `ReviewWorkbench` và `EvidenceViewer` PDF song song.
