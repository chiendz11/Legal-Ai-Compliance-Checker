# Từ điển dữ liệu PDF → C02 → module tiêu thụ

> Baseline hiện hành cho DB mới: [PDF360 v4 r2 — 10/11](../guides/dataset_pdf360_v4r2_runtime_20261110.md).
> Knowledge được chủ dự án duyệt, hash `4ab2d7ea296ea908e25c09fcb6d5f073f1ebe1917678b36390f803b1c725804a`; full-catalog reference xét 323 families.
> Số liệu PDF/TEAM_CORE của revision trước bên dưới là lịch sử; literal reference mới chưa phải legal gold toàn tài liệu.


Rules-v7 bổ sung gross_area_m2, document_stage, warranty_subject; không trộn diện
tích sàn căn hộ với dien_tich/land_area_m2. Trạng thái trong PDF không thay lựa
chọn C01 review_mode. Xem [quy ước dự thảo](../guides/baseline_v3_draft_review_fix_20261109.md).

Đặc tả máy đọc: [data_dictionary.json](data_dictionary.json). Quyết định tích hợp:
[integration_spec.md](integration_spec.md). Không chép legal text hoặc đáp án TEST
vào Git. Đây là quy ước giao tiếp, không phải một bộ gold labels mới.

Phạm vi nguồn hiện có: [baseline FULL90](source_observed_extraction_baseline.md).
Mười chín trường giao dịch được quan sát trong 90/90 bản; không yêu cầu PDF có đủ
mọi thuộc tính của schema. Producer chỉ lấy điều có nguồn; consumer giữ UNKNOWN
đúng lý do khi knowledge cần dữ kiện chưa có, không tự giảm checklist.

## 1. Mỗi dữ kiện phải có gì?

Tên chuẩn, kiểu/đơn vị, ý nghĩa, nguồn bằng chứng, người tạo, consumer, điều kiện xác
minh và hành vi khi thiếu/mâu thuẫn. C02 `profile` là thuộc tính giao dịch typed;
`facts` là các giá trị trích xuất có evidence_ids; subject giữ vai trò các bên;
time_markers giữ ngày và nguồn. Không đưa cờ kỹ thuật backend vào nội dung PDF.

| Nhóm | Nguồn → producer → consumer | Quy tắc |
|---|---|---|
| Profile | PDF/annotation phân loại có nguồn → 2 → 3 | Mọi field trong ProfileFields có entry JSON; null không phải false |
| Chủ thể | Đoạn về từng bên → 2 → 3/4 | Không suy ra tư cách kinh doanh chỉ từ tên |
| Giá | Đoạn/bảng/phụ lục → 2; mapping 4 → numeric | Decimal + currency, giữ giá ứng viên và mâu thuẫn |
| Diện tích | Mã căn/tòa/cách đo → 2 → retrieval/reasoning | Không tự đổi thông thủy sang tim tường |
| Bảo hành | Điều khoản → 2; mapping 4 → numeric | warranty_months, warranty_unit=MONTH, warranty_start có nguồn |
| Thanh toán | Lịch cam kết và biên nhận phân biệt → 2/4 → 3/4 | Lời hứa trả tiền không chứng minh đã thu |
| Thuộc tính số/rules | Backend/reviewer → 4 → C07 | numeric_scope/target/ngoại lệ/review reference không do LLM tự duyệt |

Revision tri thức 06/11 bổ sung typed fields `la_giao_dich_dien_tu` và
`co_thoa_thuan_trong_tai`. Năm scope records đổi từ `can_danh_gia_trong_tai` sang
field thỏa thuận có nguồn, không dùng một assessment switch. Người 2 vẫn phải
implement extraction/mapping: null không thành false. Chi tiết nguồn, persistence
facts và mốc áp dụng nằm trong [policy tri thức](knowledge_applicability_policy.md).

## 2. Tên facts và alias

`gia_tri_hop_dong` có trong profile không tự động đồng nghĩa `sale_price`,
`contract_price`, `apartment_value` hoặc `maintenance_base` của mọi rule. Người 4
phải xác nhận mẫu số, thuế/phí, currency và phạm vi từng criterion. JSON có danh mục
canonical facts và tám nhóm numeric schema đang được numeric_kind hỗ trợ, gồm các
nhánh legacy. Bốn mươi ba tên facts bao gồm unit/review/target, không phải 43 cột PDF.

Nhóm facts là **tập bao an toàn**, không phải mọi criterion bắt buộc dùng tất cả.
Ví dụ rule chung đặt cọc có thể dùng cho cap, eligibility hoặc yêu cầu nêu giá;
numeric_target phải được bind bằng review độc lập, không đoán từ keyword/criterion ID.
Nhánh maintenance legacy cần quyết định mẫu số và payment inclusion riêng.

Ngoài numeric facts, verification_control_fields quy định evaluation_target,
condition_triggered và optional_choice_confirmed mà reasoner đang dùng. Criterion
Verification và DocumentReadCoverage có schema riêng; đọc [recipe verifier](../modules/criterion_verification_guide.md)
để hiểu proof nghĩa vụ theo từng loại, không suy từ việc fact dict khác rỗng.

## 3. Ma trận từng criterion của snapshot đang dùng

Chạy từ root repo đã cài backend, với DATABASE_URL trỏ DB riêng đã seed/update:

```bash
python -m devtools.integration_audit --output data/private/integration_audit
```

Tool chỉ SELECT snapshot đúng hash manifest, kiểm checksum, không seed/capture snapshot,
không gọi LLM hoặc ghi DB. Kết quả private:

- `criterion_fact_matrix.csv`: mỗi criterion một hàng, family/version, loại kiểm tra,
  nhóm numeric, candidate facts, nguồn, owner và điểm chưa phân giải.
- `integration_inventory.json`: summary và scope/marker/source gaps.

Snapshot reviewed 05/11 có 441 criterion / 306 families. Rà soát lúc đó: 14 scope
records dùng hai field chưa hỗ trợ; 81 families chưa có marker mapping; hai criterion
cần review liên kết article ↔ primary document. 14 criterion có numeric rule; 427
criterion cần đọc semantic predicate/evidence policy. Số 81 toàn catalog khác 80 gặp
trong một run cụ thể. Revision KNOWLEDGE_ALIGNED 06/11 đã bổ sung mapping/mốc và
sửa primary source; phải chạy audit đúng hash của revision cần kiểm tra. Manifest
hiện pin TEAM_BASELINE_20261107 (323 families / 479 criteria), xem
[hướng dẫn baseline](../guides/dataset_team_baseline_20261107.md). DB cũ không tự đổi.
Các con số 05/11 trên là thống kê metadata lịch sử, không phải kết luận pháp lý.

Tool không tự diễn giải prose thành facts có giá trị pháp lý. Các hàng
SEMANTIC_PREDICATE_EVIDENCE_REVIEW_REQUIRED và NUMERIC_BRANCH_AND_TARGET_REVIEW_REQUIRED
là công việc cần owner xác nhận, không được báo đã có binding gold. Người 1/3/4
chốt từng binding bằng dữ liệu structured có nguồn; semantic criterion vẫn có thể
dùng evidence text thay một bộ facts số cứng khi policy cho phép.

## 4. Khi có PDF mới hoặc sửa PDF

PDF thiếu thông tin có thể là test missing cố ý. PDF đã có thông tin nhưng parser
bỏ sót thì sửa extractor/mapper. Với corpus 90 mẫu hiện hành, giữ nguồn đã điền
làm đầu vào cố định; không viết thêm điều khoản/phụ lục/chứng từ để ép đủ field.
Các nhánh thiếu nguồn giữ uncertainty theo policy. Không ghi nhãn
SATISFIED/VIOLATED hoặc gates vào PDF.

Nếu bytes đổi: source SHA/URL revision mới → text/extraction/chunks/citation offsets
→ retrieval/evidence/annotations → workbook/QA → checksums/manifest. Không ghi đè
report lịch sử. Updater reviewed hiện từ chối xóa business rows, không tự bảo đảm một
release đổi toàn bộ chunk IDs có thể update tại chỗ; thử trên DB riêng, thiết kế
migration/reseed baseline mới và giữ dữ liệu dev trước khi áp dụng.


## Controls của kịch bản synthetic

Source của các controls này là scenario hash-bound, không phải output LLM hoặc
field bắt người dùng nhập trong PDF. Chỉ có hiệu lực khi bật rõ
SYNTHETIC_SCENARIO_PATH và đúng PDF/knowledge SHA.

| Field trong CriterionVerification.facts | Kiểu | Ý nghĩa |
|---|---|---|
| synthetic_evaluation | bool | Attestation đồ án, không phải human approval |
| scenario_document_set | string | Mã bộ tài liệu giả lập |
| synthetic_non_applicability_reason | string | Lý do local NO_MATCH của criterion; không đổi scope C05 |

[Chế độ synthetic và cách kiểm tra](../guides/synthetic_evidence_and_inference_fixes_20261107.md).

## Bổ sung rà toàn văn ngày 08/11/2026

Ba facts text tài khoản bảo trì: `maintenance_account_number` (số),
`maintenance_account_holder` (tên), `maintenance_bank` (tổ chức tín dụng). Người 2
trích literal kèm C02 evidence; người 3 dùng làm candidate, người 4 kiểm semantics.
Không thay bằng tài khoản nhận tiền mua nhà. Các control fields của full review
được định nghĩa trong `document_review_control_fields` của JSON cùng thư mục.
Không coi control field là dữ kiện phải điền thêm vào mọi PDF.

Producer `documents.rules-v10` (10/11/2026) đọc cả một dòng có dấu `;` và ba dòng
nhãn riêng: `Tài khoản bảo trì`, `Tên tài khoản bảo trì`, `Ngân hàng tài khoản bảo trì`.
Evidence giữ cả nhãn và giá trị để chứng minh đúng vai trò; không chỉ lưu số/tên
rời rồi mặc nhiên coi đó là tài khoản bảo trì. Nhiều giá trị khác nhau giữ CONFLICT.
Nhãn chấp nhận khoảng trắng ngang lặp do PDF căn đều; giá trị có thể xuống tối đa
ba dòng tiếp theo trong cùng chunk, nhưng phải kết thúc trước nhãn tài khoản kế
tiếp. Không nối qua tiêu đề, chú thích hoặc sang chunk khác. Canonical value gộp
khoảng trắng; quote/offset vẫn dùng nguyên văn nguồn.
`TC_ACCOUNT_2015_03` có nhánh kiểm nội dung hữu hạn khi đủ ba facts khớp source,
selected C06, context và version 2015. Nhánh này không xác nhận mở tài khoản,
chủ tài khoản thực tế hoặc giấy phép của tổ chức tín dụng.

## Thông tin bổ sung COMPLETE_R4

C02 `co_thoa_thuan_dat_coc` là bool/null có nguồn tường minh. Facts text:
`dia_chi_ben_ban`, `dia_chi_ben_mua`, `land_address`, `land_parcel_no`, `land_map_sheet`;
facts số `land_area_m2` (m²), `maintenance_amount` (VND), `maintenance_percent` (đơn vị
phần trăm, giá trị 2 nghĩa là 2%); dates ISO `warranty_start_date`, `acceptance_date`.
Thiếu/conflict/sai quote không được chuyển thành có dữ kiện. Người 2 trích xuất,
người 3 chọn C06, người 4 kiểm nội dung, người 5 compose trước C07.

Không thêm cột SQL `ho_so_hop_dong.co_thoa_thuan_dat_coc`: lưu fact
`profile.co_thoa_thuan_dat_coc` trong `trich_xuat_truong` và evidence trong
`bang_chung_truong`. Khi đọc C02 đã lưu, lấy profile từ snapshot extraction;
nếu JOIN SQL thì dùng đúng fact key và evidence của extraction đang xét.

## Bổ sung rules-v8 và mốc C01 ngày 09/11/2026

`maintenance_base_reference=STATED_SALE_PRICE` là fact có quote dẫn chiếu mẫu số;
không đồng nhất mọi giá hợp đồng với mẫu số bảo trì luật định. Suy luận
`co_thoa_thuan_trong_tai=False` có method `COMPLETE_DRAFT_COURT_ONLY_V1` chỉ nói về
bộ dự thảo được khai báo đủ và đọc đủ trang, giữ DERIVED_REVIEW_PENDING và
human_verified=false. Không dùng cho FULL_ASSESSMENT hoặc kết luận về hồ sơ ngoài.

`moc_ap_dung` và `loai_moc_ap_dung` trong C01 là khai báo người gọi, không phải
facts PDF. C05 giữ `assessment_marker` riêng; loại mốc phải khớp, ngày mâu thuẫn
vẫn UNKNOWN. Các control `local_condition_policy`, `condition_review_sha256` và
`condition_review_assessment` do backend tạo từ artifact toàn văn, không do người 2
trích từ PDF hoặc LLM tự xác minh.

[Binding, ownership và cách đọc kết quả](../guides/remaining_verification_alignment_20261109.md).

C09 bổ sung [policy định danh V2](citation_identity_policy.json): giữ riêng observed C03 với identity đã phân giải; tên/năm và anchor có provenance, không tự chọn bản đang hiệu lực. HYC015_02 dùng evidence nội quy/hiệu lực đúng nguồn, không lấy C01 làm dữ kiện PDF.
