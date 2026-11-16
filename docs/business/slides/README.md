# Slide báo cáo và trạng thái nội dung

Các file PPTX/PDF nhỏ được lưu trong Git để cả nhóm tải và chỉnh sửa. Dataset,
PDF hợp đồng, đáp án Gold, cache model và API key vẫn được giữ ngoài Git.

| Tài liệu | Trạng thái và cách sử dụng |
|---|---|
| [Tuần 9](bao_cao_tien_do_tuan_9.pptx) | Báo cáo/mục tiêu lịch sử; tỷ lệ kỳ vọng không thay bằng chứng nghiệm thu |
| [Tuần 10 — PPTX](bao_cao_tien_do_tuan_10.pptx) · [PDF](bao_cao_tien_do_tuan_10.pdf) | Đã đồng bộ với [báo cáo Markdown](../bao_cao_tien_do_tuan_10.md) ngày 16/11/2026; MVP, dataset, phạm vi demo và điều kiện benchmark |
| [Tuần 11 — PPTX](bao_cao_tien_do_tuan_11.pptx) · [PDF](bao_cao_tien_do_tuan_11.pdf) | Kế hoạch so với tiến độ/bằng chứng thực tế; xem [báo cáo Markdown](../bao_cao_tien_do_tuan_11.md) |
| [Báo cáo tổng quan hệ thống 16/11/2026 — PPTX](Legal-AI-Compliance-Checker-bao-cao-he-thong-2026-11-16.pptx) | Bản trình bày tổng hợp hệ thống (BA, Contracts C01–C13, Kiến trúc, Stack, Gold Master R12, QA & lộ trình), đã bổ sung tùy chọn `DOCUMENTS_EXTRACTOR=hybrid` (Qwen/Ollama) |
| [Kho tri thức pháp lý](bao_cao_kho_tri_thuc_phap_ly.pptx) | Bản nháp lịch sử, đã đóng dấu trên từng slide; các nhận định pháp lý, độ bao phủ và tỷ lệ tuyệt đối chưa được nghiệm thu toàn bộ |
| [Công nghệ C01–C13 (Deep Dive)](cong_nghe_va_ky_thuat_he_thong_c01_c13.pptx) | Đã chuẩn hóa và đồng bộ với [`docs/system-guide/`](../../system-guide/README.md) & Gold Master R12 ngày 17/11/2026 (bỏ các số `100%/F1=1.00` lịch sử, đồng bộ Python 3.12 / React 19 / `DOCUMENTS_EXTRACTOR=hybrid` Qwen local / Kleene C04 / Điều 83(5) C05 / `AGG_CAN_HO_V1` / C12 target hash) |
| [Quy trình Gold](quy_trinh_xay_dung_golden_dataset.pptx) | Bản nháp lịch sử; quy trình mục tiêu và số liệu cũ không chứng minh Gold đã hoàn tất hoặc TEST đã được giữ kín |

Hai bản nháp lịch sử (`bao_cao_kho_tri_thuc_phap_ly.pptx`, `quy_trinh_xay_dung_golden_dataset.pptx`) được giữ để nhóm tiếp tục sửa; không dùng chúng như báo cáo kết quả
chính thức. Bản trước khi thêm dấu được giữ riêng ở máy local trong
`data/private/publish_worktree_20261116/before/`.

Hiện trạng Gold được ghi trong [guide Gold Master](../../guides/gold_master_20261114.md).
Ngày 16/11/2026: R12 có 220/360 ca đã biên soạn, 140 ca còn chờ;
`full_e2e_gold_ready=false`, `AI_SOURCE_ADJUDICATED`, `human_legal_signoff=false`.
Không suy các phép kiểm scoped thành độ chính xác pháp lý toàn bộ corpus.

Các bản PPTX cùng tên trong `docs/business/` và `docs/business/slides/` có nội dung
giống nhau để giữ các liên kết cũ. Khi sửa, cập nhật đồng thời hai bản. PDF tuần 10
và 11 là bản xem từ cùng nội dung/bố cục dựng slide; PPTX là bản chỉnh sửa.
