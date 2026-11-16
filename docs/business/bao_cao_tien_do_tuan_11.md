# Báo cáo tuần 11 — Kế hoạch và tiến độ thực tế

Cập nhật ngày 16/11/2026. Đối chiếu [workbook kế hoạch](ke_hoach_10_tuan.xlsx), sheet `02_KeHoach_ChiTiet_10Tuan` dòng 40–44 và sheet `05_MucTieu_Backlog_QuyTac` dòng 10.

[PowerPoint chỉnh sửa được](bao_cao_tien_do_tuan_11.pptx) · [PDF để xem](slides/bao_cao_tien_do_tuan_11.pdf).

## Nội dung báo cáo dễ hiểu

Đã có các chức năng chính để đọc hợp đồng, đánh giá và hiển thị báo cáo trên Web. Nhóm đã bổ sung kiểm tra nguồn, cách báo thiếu dữ kiện, phân quyền, rà soát kết quả và xử lý tác vụ bị lỗi hoặc gửi trùng.

Hiện đang kiểm tra nhiều tình huống trên cùng một bản code và dữ liệu, đồng thời chuẩn bị gói bàn giao để các thành viên có thể dựng lại môi trường. Còn chốt phạm vi hỗ trợ PDF/OCR, phát hành dataset và nghiệm thu hành trình E2E trước khi xác nhận hệ thống ổn định.

**Đánh giá chung: có phần lớn chức năng cần cho tuần 11, đang hoàn tất kiểm tra và bàn giao; chưa chốt toàn bộ tiêu chí Inference STABLE.** Không tự quy đổi thành phần trăm khi chưa có kết quả nghiệm thu từng đầu việc.

## Kế hoạch so với thực tế

| Người | Kế hoạch tuần 11 | Thực tế đã có | Phần còn lại để bàn giao |
|---|---|---|---|
| 1 — Data/DevOps | Dữ liệu và platform release candidate; dựng lại từ checkout mới; seed/CI/GitOps ổn định | Dataset có phiên bản/checksum; Alembic, seed và CI; có hồ sơ seed 300 ca DEV/VALIDATION vào DB kiểm tra riêng | Phát hành URL dataset; chốt commit và cấu hình; kiểm checkout mới → migrate/seed → build/test → triển khai đúng revision |
| 2 — Documents | Sửa lỗi OCR/layout/source refs; đo extraction/chunk/citation so với technical refs; công bố giới hạn | Parser PDF có text, profile/facts, chunks theo cấu trúc, citations và quote/offset; có phép kiểm kỹ thuật trên 60 PDF VALIDATION | OCR chưa triển khai; chốt phạm vi hỗ trợ; tổng hợp QA và xử lý lỗi đọc nghiêm trọng, không biến parser failure thành dữ liệu thiếu |
| 3 — Legal/Retrieval | Regression scope/time/citation; đo retrieval candidates/latency; tránh kết luận chắc chắn sai | Resolver, chính sách định danh, retrieval có ngữ cảnh và các tests về ngày/version/nguồn mơ hồ | Báo cáo QA trên baseline chốt; kiểm evidence, độ trễ và nguyên nhân bỏ sót; không tune bằng validation labels rồi gọi là đánh giá độc lập |
| 4 — Reasoning | Schema validity, grounding, guardrails, rule consistency; prompt có version | Verifier, kiểm quote, coverage toàn văn, numeric rules, prompt version và xử lý các lỗi cụ thể | Kiểm các nhãn và tình huống thiếu/mâu thuẫn/vi phạm; phân biệt lỗi provider/hết lượt với thiếu căn cứ pháp lý |
| 5 — Web/Orchestrator | E2E ổn định, AuthN/AuthZ, Human Review có audit, retry/idempotency | Có code auth/tenant/role, Reviewer Workbench, publish gate, heartbeat/recovery; integration tests và biên bản demo PDF thật | Nghiệm thu nhiều PDF cùng release; auth thật; sửa nhãn → audit → report → publish; gửi trùng/lỗi worker/phục hồi trên queue thật |

Đây là trạng thái phần việc mỗi người phụ trách, không phải xác nhận tác giả từng commit. Các ô “0% / Chưa bắt đầu” trong workbook là trạng thái kế hoạch cũ, không dùng để phủ nhận implementation hiện có.

## Bằng chứng và giới hạn

- **Data/seed:** `data/private/v750_pdf360_v4r2_runtime_20261110/SEED_QUALIFICATION.json` ghi seed 300 ca vào DB test riêng, cùng kết quả chạy lại nhận đã seed. Chứng minh nạp dữ liệu, chưa chứng minh mọi module inference đúng. [Manifest tải](../../configs/dataset_dev_validation.json) hiện ghi `LOCAL_ARCHIVE_READY`, `archive.url=null`; chưa có link tải tự động cho bản này.
- **Documents:** `data/private/legal_methods_trial_20261109/validation/summary.json` ghi 60/60 PDF vượt bộ kiểm kỹ thuật và citation boundary cuts từ 16 xuống 0. Không diễn giải thành độ chính xác pháp lý 100%. [OCR](../../backend/src/legal_checker/modules/documents/ocr.py) vẫn chưa triển khai.
- **Legal/Reasoning:** có regression cases trong `test_catalog_legal_policy.py`, `test_citation_identity_v2.py`, `test_source_chunking_context.py`, `test_source_verifier.py` và `test_c07_hardening.py`. Sự tồn tại của tests chưa tự chứng minh phiên bản checkout hiện tại đã chạy pass toàn bộ.
- **Auth/Review/Queue:** có `test_auth.py`, `test_reviews.py` và `test_assessment_runs.py`. Test workflow có dùng synthetic step adapters để kiểm điều phối; không coi đó là nghiệm thu chất lượng suy luận trên PDF thật. Mẫu `.env` đặt auth off; điều này không chứng minh cấu hình runtime đang off, nhưng nghiệm thu auth cần bật rõ.
- **Demo:** [biên bản ngày 10/11](../guides/baseline_v4_acceptance_20261110.md) ghi upload PDF thật → queue → modules → tám tab báo cáo và export. Run `RUN_dfd704ad7c3c455ab067d07534bb76dc`, report `REPORT_48da32fb-461e-579f-9fe8-c811f1f08b42`. Đây là run lịch sử với source/knowledge/extractor riêng, không tự xác nhận các thay đổi mới.
- **Gold:** [Gold Master R12](../guides/gold_master_20261114.md) có 220/360 ca đã biên soạn, 140 ca còn chờ; `full_e2e_gold_ready=false`, `human_legal_signoff=false`. Đánh giá được trong phạm vi đáp án đã chấm; chưa công bố benchmark pháp lý toàn bộ corpus. Gold chưa hoàn tất không ngăn QA kỹ thuật tuần 11.

Báo cáo dựa trên code và artifact đang có, gồm bằng chứng tích lũy trước tuần 11; không quy toàn bộ thành công việc mới làm riêng trong tuần. Đợt lập báo cáo này không chạy thêm test, benchmark, model, demo hoặc kiểm tra cluster. Không xác nhận CI/GitOps đang healthy chỉ từ tài liệu lịch sử. Workbook kế hoạch được giữ nguyên.

## Những việc cần hoàn tất theo thứ tự

1. **Người 1 chốt bản bàn giao:** commit, dataset, checksum, URL tải và cấu hình. Chạy quy trình dựng lại trên môi trường riêng, giữ dữ liệu phát triển hiện có.
2. **Người 2–4 tổng hợp regression:** chạy các kiểm tra cần thiết, sửa lỗi quan trọng, ghi giới hạn và lỗi còn mở. Không ghi SKIP thành PASS.
3. **Người 5 chủ trì nghiệm thu tích hợp:** PDF đủ thông tin; thiếu/mâu thuẫn; luật/viện dẫn; auth/review; gửi trùng/lỗi job. Dùng module thật, ghi ca/run/report và source/knowledge/model/prompt pins.
4. **Cả nhóm đối chiếu tiêu chí:** không còn lỗi nghiêm trọng chặn luồng; lỗi còn lại có owner, nguyên nhân và hướng xử lý. Khi đó mới chốt stable release.

| Tình huống nghiệm thu | Kết quả cần có |
|---|---|
| PDF đủ thông tin | Tới report, có evidence, đúng contract/case/run/hash |
| Thiếu thông tin hoặc mâu thuẫn | Không tự đoán, lý do chưa kết luận đúng |
| Scope/time/citation | Luật áp dụng độc lập citation; version rõ hoặc UNKNOWN có lý do |
| Auth và rà soát | Sai quyền bị chặn, sửa nhãn có audit, publish đủ điều kiện |
| Gửi trùng, lỗi worker/provider | Không tạo việc trùng, lỗi rõ, retry/recovery đúng giới hạn |

Bảng trên là checklist cần nghiệm thu; không phải tuyên bố mọi tình huống đã PASS. “Chưa có bằng chứng” cũng không đồng nghĩa đã xác nhận có lỗi.
