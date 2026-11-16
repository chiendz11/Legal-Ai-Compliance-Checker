# Bàn giao main và công việc tiếp theo cho 5 người

> Dataset cho DB phát triển mới: [PDF360 v4 r2 — 10/11](dataset_pdf360_v4r2_runtime_20261110.md).
> Dùng PDF cùng hash, snapshot đã duyệt; các hướng dẫn migration của release cũ chỉ áp dụng cho release tương ứng.


Baseline dữ liệu mới: [PDF360 v4 r2 — 10/11](dataset_pdf360_v4r2_runtime_20261110.md). Lần này seed DB mới, giữ DB/lịch sử cũ; không dùng lệnh update dành cho reviewed-flags-only release.

Cập nhật ngày **07/11/2026**. Baseline mới hiện nằm trên nhánh tích hợp, chưa được
publish/merge chỉ bằng việc cập nhật tài liệu. Ownership theo `docs/business/ke_hoach_10_tuan.xlsx`; không suy ra tác giả
thực tế của từng commit hoặc phần trăm hoàn thành từ tên người phụ trách.

Hướng dẫn thao tác từng người: [playbook hiện hành](parallel_development_playbook.md). Definition of Done và qualification được kiểm theo ma trận, không đóng task chỉ vì đã có port. [Biên bản thống nhất docs](docs_alignment_changes_20261107.md) phân biệt các mâu thuẫn đã sửa với implementation/chất lượng còn phải bàn giao.

Quyết định mới nhất: [INTEGRATION_V1](../contracts/integration_spec.md), [dictionary](../contracts/data_dictionary.md) và [changelog tích hợp](integration_alignment_changes_20261105.md).
Các backlog dưới đây mô tả chẩn đoán trước gói alignment; xem changelog để biết điểm nối đã sửa và phần còn cần nghiệm thu.

## 1. Lấy code và baseline

Tài liệu/runtime mới nằm trên feat/integration-contract-alignment trong working tree;
maintainer cần publish code trước khi đồng đội fetch. Các bằng chứng phase-two bên
trên mô tả lần triển khai cũ, không tự bao gồm release dữ liệu 07/11.

## 2. Cài dataset và DB mới

Làm theo [PDF360 v4 r2 — 10/11](dataset_pdf360_v4r2_runtime_20261110.md): cập nhật hai biến
DATABASE_URL/SEED_WORKBOOK_PATH, cài ZIP DEV/VALIDATION, init/seed/check trên DB mới.
Giữ DB cũ và cấu hình/secrets riêng. Không dùng update của reviewed-flags release.
Manifest mới HUMAN_VERIFIED theo quyết định chủ dự án; LOCAL_ARCHIVE_READY cho biết ZIP chưa được xác nhận xuất bản trên Drive. Không đổi sang PUBLISHED để bỏ kiểm tra. Chạy thêm `python -m scripts.dataset cache-sources` để đọc PDF v4 r2 đóng kèm. Không dùng URL Supabase v2 cho workbook mới.

## 3. Bằng chứng cần giữ

Dataset/workbook/knowledge/source hashes, receipt seed và context của các run mới.
Dữ liệu QA là reference; không thay output live hoặc báo accuracy với expected
được dựng bởi chính engine. Group 3–5 dùng scope/topic mapping của baseline mới.

## 4. Thứ tự tích hợp và cách đóng task

1. Maintainer publish code baseline; cả nhóm lấy revision đó và đồng bộ dataset/DB. Mỗi người xác nhận hash.
2. Persistence Documents trước Retrieval đã nối trong code; người 2 + 3 + 5 nghiệm thu producer/consumer thật, không xây writer trùng.
3. Catalog TEAM đã có policy marker/version; người 1 + 3 dùng đúng snapshot, người 2 cung cấp profile/time markers có nguồn. Ca thiếu dữ kiện/chuyển tiếp chưa support giữ lý do riêng.
4. Cổng verifier đã nối; người 4 bàn giao implementation kiểm facts/predicate thật, người 5 inject vào API và worker, người 3 bảo đảm selected evidence đúng run/criterion.
5. Live provenance C09→C10 đã có; người 3 + 4 + 5 nghiệm thu pins và SOURCE_CHECKED gate. Người 4 + 5 xử lý budget/retry/thông điệp, không suy lỗi kỹ thuật là thiếu hồ sơ.
6. Chạy ca DEV đại diện sau từng điểm nối, lưu code SHA + dataset/hash + model/prompt +
   output/diagnostics. Sau đó chạy validation và công bố metrics theo từng module.

Mỗi task có PR, test hoặc bằng chứng phù hợp, input/output contract, IDs/version/hash
và lỗi còn lại. Phân biệt unit/fixture pass, provider thật, integration và đánh giá
chất lượng. Không dùng tỷ lệ hoàn thành tự đặt hoặc mọi trạng thái COMPLIANT làm gate.

## 5. Main ứng dụng và Argo CD

Merge app vào main giúp cả nhóm dùng baseline mới; không tự merge hai repo infra/GitOps
và không tự đổi nhánh Argo CD đang theo dõi. Cụm local hiện theo GitOps feature branch
phase-two. Workflow publish của app trên main mặc định cập nhật GitOps main; đó là
nhánh riêng với nhánh đang chạy local. Nếu cần rollout image mới lên local hiện tại,
dùng dispatch chỉ rõ `target_branch=feat/local-phase2-worker-verification` và kiểm tra
image/Argo health sau đó. Không tự chuyển Argo sang GitOps main còn cấu hình phase-one.

Không cần k3d để dev từng module. Cụm local là môi trường tích hợp; PostgreSQL local
riêng và contracts/fixtures là nền cho phần việc song song.
