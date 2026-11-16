# Rà soát dự thảo PDF v3 — quy ước tích hợp 09/11/2026

## 1. Nguyên nhân và cách xử lý

Run v3 đầu tiên có 129 C07 UNKNOWN: catalog đặt `case_facts_required=true` cho
mọi criterion, còn verifier chỉ chấp nhận nhánh không có cờ này. Scenario demo cũ
được khóa theo PDF SHA cũ, không phải verifier tổng quát cho PDF mới.

Giải pháp: người dùng chọn rõ mục đích ở C01; workflow giữ receipt
case/run/contract/PDF/knowledge/policy. Không thay SHA scenario cũ hoặc nạp lại
biên nhận thực thu giả vào hồ sơ dự thảo.

## 2. C01 và API

`POST /api/v1/cases` nhận thêm:

```json
{
  "hop_dong_id": "ID_DO_BACKEND_TRA_VE_SAU_UPLOAD",
  "ngay_danh_gia": "2026-11-09",
  "review_mode": "DRAFT_REVIEW",
  "document_set_complete": true
}
```

API mặc định FULL_ASSESSMENT để giữ hành vi cũ. UI cho chọn cả FULL_ASSESSMENT
và DRAFT_REVIEW. document_set_complete mặc định false: khai báo đủ thân và phụ
lục trong phạm vi rà soát, không phải phê duyệt kết quả hoặc xác nhận giao dịch.
Actor/tenant do backend xác định; một câu trong PDF không được đổi chế độ.

Alembic `0008_assessment_review_scope` thêm hai cột vào runtime.ca_danh_gia;
CaseRepository và DocumentRepository đọc cùng giá trị. Case cũ giữ FULL/false.
Deserialize reports cũ không thêm hai field mặc định vào dữ liệu đóng băng để
tránh đổi digest lịch sử.

## 3. Người 2 — dữ kiện tài liệu

| Fact | Ý nghĩa | Nguồn/đơn vị |
|---|---|---|
| dien_tich | Diện tích sử dụng căn hộ | Nhãn riêng, m², Decimal dạng string |
| gross_area_m2 | Diện tích sàn xây dựng căn hộ | Nhãn riêng, m², không suy từ đất |
| land_area_m2 | Diện tích thửa đất | Nhãn riêng, m² |
| document_stage | Trạng thái tài liệu tự khai | DRAFT_REVIEW có quote; không phải lựa chọn vận hành |
| warranty_subject | Nhà ở hay thiết bị | BUILDING khi nguồn thời hạn nói rõ nhà ở/căn hộ |

Rules-v7 giữ quote/offset/active chunk; thiếu hoặc mâu thuẫn không tự điền.
human_verified vẫn false. Extraction version mới sinh IDs mới, tránh giữ facts
cũ qua ON CONFLICT.

## 4. Người 3 — C05 và C06

C04/C05 vẫn phân giải catalog theo facts/mốc đúng nguồn. Dự thảo không đổi UNKNOWN
thành CONFIRMED hoặc lấy ngày ký thay mọi sự kiện thực tế. Workflow bổ sung
assessment_review riêng trên C05: context, source SHA, actor khai báo,
policy SHA và đích đánh giá từng criterion; không thay scope/version gốc.
profile_snapshot_json, dieu_kien_snapshot_json và nguon_snapshot_json của producer
pháp lý không bị sửa. Handoff được kiểm ngay trước lượt refinement/LLM có trả phí,
rồi kiểm lại cùng nhánh citation trước C07–C13.
Receipt riêng theo run được lưu trong input snapshot và được khóa bằng checksum;
không thêm cột vào workbook hay ghi đè dòng C05 pháp lý dùng chung giữa các run.

Retrieval thêm bindings diện tích sàn, thửa đất, địa chỉ từng bên và khoản bảo trì.
Candidates từ rà toàn văn phải quay lại C06 và qua membership/quote checks.
Criterion ngoài phạm vi không gọi LLM để tìm biên nhận không được cung cấp.
Thiếu adapter hoặc C05 chưa xác nhận nhận diagnostic rõ nguyên nhân; không gắn
một chunk bất kỳ để che việc chưa có evidence liên quan.

## 5. Người 4 — verifier và C07

Policy máy đọc: [draft_review_policy.json](../contracts/draft_review_policy.json).
Implementation: modules/compliance/review_scope.py.

- CONTRACT_TEXT/NOI_DUNG_HOP_DONG_THEO_MAU và bindings hỗn hợp đã đăng ký được
  kiểm nội dung. case_facts_required được đáp ứng bằng nguồn/đích đã kiểm, không
  dùng làm cờ chặn vĩnh viễn.
- Bindings hỗn hợp liệt kê theo ID và facts tiên quyết. Nhánh chưa có binding
  vẫn UNKNOWN, không diễn giải tùy ý bằng keyword.
- Việc ký/đóng dấu, thực thu, bàn giao, thiệt hại, quyền sở hữu hoặc hồ sơ bên
  ngoài nằm ngoài phạm vi này. Companion predicates về điều khoản vẫn được kiểm
  khi có binding riêng; danh sách được lưu trong policy để review.
- Ngoại lệ thiếu adapter hoặc dữ kiện vẫn chặn kết luận. Condition tree chỉ xác
  nhận một ngoại lệ không phát sinh khi nguồn cho kết quả FALSE; UNKNOWN không
  là FALSE. MATCH vẫn cần adapter áp dụng effect.
- SOURCE_CHECKED được dùng cho bản nháp nội dung theo policy rõ ràng, legal basis
  hợp lệ; không đổi knowledge hoặc output thành HUMAN_VERIFIED.
- MISSING/khẳng định vắng điều khoản cấm cần full-document artifact, tất cả chunks
  được đọc, khai báo đủ phụ lục và các gates khác. Checkbox một mình không đủ.
- Rà toàn văn chia cả nhóm nguồn và nhóm criterion (tối đa 12 criterion/lượt),
  rồi ghép lại ma trận đầy đủ. Mỗi nhóm criterion phải xác nhận đọc đủ nhóm nguồn;
  thiếu một ô hoặc nguồn lạ sẽ không tạo proof vắng nội dung. Schema giới hạn đúng
  aliases/số phần tử; lượt sửa nhận manifest cần trả, không tự điền kết quả thiếu.
- Điều khoản miễn trách nhiệm cho tranh chấp do hành vi bên mua không tự chứng minh
  bên bán loại trừ trách nhiệm khi bán qua môi giới/đại lý. Predicate về trung gian
  phải có evidence đúng quan hệ đó; guard chỉ chặn kết luận sai chủ thể, không tự
  biến thành SATISFIED.
- TC_PV_HYC040_04 kiểm riêng hai diện tích căn hộ từ C02 có quote/offset; không
  lấy diện tích đất làm số còn thiếu.
- Khi context quá lớn, phần chữ trùng giữa chunk và quote catalog được biểu diễn
  một lần bằng các dòng `[quote_id, text]` có thứ tự. Giữ cả dòng ngắn/dòng trống;
  nối lại phải khớp chính xác chunk gốc. IDs và offsets backend không đổi, không
  bỏ đoạn nguồn hoặc tự xác nhận coverage từ việc rút gọn prompt.
  `ASSESSMENT_LLM_MAX_CONTEXT_CHARS` cấu hình ngân sách mỗi criterion (mặc định
  80.000 ký tự, khác token); phải chọn theo model thực tế. Sau rút gọn vẫn vượt
  ngân sách thì báo CONTEXT_LIMIT, không cắt mất evidence hoặc tự kết luận.

Nhánh ngoài phạm vi vẫn giữ C07 UNKNOWN + excluded + lý do REVIEW_SCOPE_EXCLUDED,
model BACKEND_REVIEW_SCOPE_V1; không giả lượt gọi LLM hoặc sự kiện đã xảy ra.

## 6. Người 5 — báo cáo và UI

C08 giữ bốn status pháp lý. assessment_disposition=OUTSIDE_REVIEW_SCOPE được
hiển thị riêng là **Ngoài phạm vi rà soát dự thảo**, khác NOT_TRIGGERED,
NOT_APPLICABLE và COMPLIANT. Mixed requirement tổng hợp criterion còn trong phạm
vi; snapshot vẫn giữ danh sách đã loại/lý do, không hiểu là kiểm toàn bộ nghĩa vụ.

C13/audit ghi review_mode, khai báo đủ tài liệu và policy. FE có lựa chọn khi
upload, nhãn header, phân bổ và thẻ criterion/requirement. Output vẫn DRAFT/PENDING;
review/publish dùng C12, không tự CONFIRM.

## 7. Nâng cấp và chạy lại

Không cần seed workbook để thêm hai cột vận hành:

```bash
source .venv/bin/activate
python -m scripts.local_db init
```

Lệnh tác động DATABASE_URL đang cấu hình. Với k3d phải migrate đúng DB mà Secret
trỏ tới; API/worker/Beat dùng cùng image mới, frontend dùng build/types mới.
Tạo case/run mới, chọn DRAFT_REVIEW. Chỉ khai báo đủ tài liệu sau khi kiểm bộ
thân/phụ lục đầu vào. Không sửa báo cáo cũ để thể hiện thay đổi code mới.

Đây không phải phát hành lại workbook TEAM hoặc thay URL/SHA của 360 nguồn đang
seed. Upload PDF v3 tạo nguồn mới, SHA mới. Bằng chứng riêng tư của lần kiểm tra
nằm ở data/private/baseline_v3_fix_20261109/.

## 8. Kết quả chạy thật trên k3d local

Kết quả dưới đây thuộc **một run đã hoàn tất**, không phải đáp án seed hoặc replay:

- Case: `CA_UP_0E091A3A1817`.
- Run: `RUN_337e2405995f4fb1b6aeff60b948eb0e`.
- Report: `REPORT_d709c2bf-64d3-529c-8a99-84469324d4e0`.
- [Mở tab Tuân thủ](http://app.legal-checker.localhost:18880/reports/REPORT_d709c2bf-64d3-529c-8a99-84469324d4e0?tab=compliance).
- PDF SHA-256: `9bac4ac8ae4a2e71584c8b421bce6106b3a3cec54061bfc678e869f2430b8e97`.
- Knowledge SHA-256: `32d59bcb9efe506389543bae5ee819d2d07d4a322425fa2d3ffa377c1eff698b`.
- Mode: `DRAFT_REVIEW`; kết luận chỉ về nội dung dự thảo.

| Phần | Kết quả |
|---|---|
| Document Intelligence | 78 trang, 139 chunks, 54 facts |
| Dữ kiện diện tích | Sử dụng 62,4 m²; sàn xây dựng căn hộ 67,4 m²; thửa đất 17.000 m², giữ riêng nguồn |
| C05 | 73 CONFIRMED, 242 NOT_APPLICABLE, 8 UNKNOWN |
| C07 hiển thị | 78 đáp ứng, 16 chưa xác định, 35 ngoài phạm vi dự thảo |
| C08 hiển thị | 51 tuân thủ nội dung, 17 chưa đủ căn cứ, 13 ngoài phạm vi dự thảo |
| Không tuân thủ | 0 trong run này |
| C09 | 5 VALID, 7 UNKNOWN |
| C10/C11 | 23 mục cần xác minh, liên kết với 23 khuyến nghị |
| Rà toàn văn | Ma trận đầy đủ cho 47 criteria trên 139 chunks, 4 nhóm nguồn |

Lưu ý cách đọc contract: raw C07 vẫn có 51 UNKNOWN, gồm 35 criterion bị loại khỏi
phạm vi và 16 criterion chưa kết luận. Raw C08 có 30 INSUFFICIENT, gồm 13 yêu cầu
ngoài phạm vi và 17 yêu cầu thiếu căn cứ. UI và export phân biệt chúng bằng
`assessment_disposition`; không đổi enum pháp lý chỉ để hiển thị đẹp hơn.

Đã đối chiếu 248 quote với nội dung/offsets trong active chunks; kiểm tra 323 C05
receipts cùng case/run/contract/source/knowledge/policy; kiểm tra risk và recommendation
không nối nhầm run. PDF ứng dụng phục vụ khớp SHA nguồn; JSON export khớp report
lưu trong DB, PDF export có cấu trúc PDF hợp lệ.

Cả tám tab mở thành công, không có JavaScript error hoặc HTTP lỗi trong hành trình
browser; export JSON/PDF trả 200. Không tạo review CONFIRM/OVERRIDE hoặc publish.
Báo cáo vẫn DRAFT/PENDING. Không sử dụng scenario biên nhận giả định 75%/98%.

Diagnostics của run không còn `VERIFICATION_PROVIDER_NOT_CONFIGURED`,
`DOCUMENT_REVIEW_INVALID_MATRIX`, `NO_SELECTED_C06`, `CONTEXT_LIMIT`, `CALL_LIMIT`,
`INVALID_SCHEMA` hoặc `INVALID_BATCH_RESPONSE`. Audit ghi 32 lượt provider thành
công và một lần RATE_LIMIT được retry; lỗi tạm thời không thành lỗi criterion cuối.

Kiểm tra code: 1.588 backend tests pass, 7 skip; Ruff pass; frontend TypeScript/Vite
build pass. Đây là kiểm tra local, không phải kết quả CI của commit đã push.
Migration k3d đã ở `0008_assessment_review_scope`. 12 báo cáo có trước bản sửa giữ
nguyên raw JSON và checksum. Workbook, PDF và knowledge pin không bị sửa.

API/worker/scheduler dùng backend image `832e58b9…`; frontend dùng `23878ec2…`.
Cả bốn deployment Ready. Đây là image build từ worktree local; chưa commit/push
hoặc publish GHCR. Argo applications Healthy/OutOfSync và auto-sync đang tạm dừng
để giữ bản local, chưa phải trạng thái GitOps Synced.

## 9. Backlog lịch sử của run ở mục 8

Các đầu việc trong mục này mô tả run lịch sử ở mục 8. Bản sửa tiếp theo và kết quả
run mới nằm tại [hoàn thiện điều kiện/mốc/numeric](remaining_verification_alignment_20261109.md);
không dùng bảng dưới đây làm backlog hiện hành nếu chưa đối chiếu bản cập nhật.

Ở thời điểm run lịch sử, pipeline đã chạy hết, nhưng verifier chưa bao phủ toàn bộ nghiệp vụ trong catalog.
Không được gọi 17 yêu cầu thiếu căn cứ là đã xử lý hoàn toàn hoặc quy tất cả về PDF
thiếu thông tin. Trong run trên, 17 yêu cầu gồm **9 NEEDS_EVIDENCE + 8
LEGAL_SCOPE_UNRESOLVED**.

| Nhóm còn lại | Chi tiết và việc cần làm | Owner |
|---|---|---|
| 7 criterion chưa có adapter điều kiện | `TC_PV_DS418_01`, `TC_PV_DS418_02`, `TC_PV_DS435_02`, `TC_PV_DS442_02`, `TC_PV_DS444_02`, `TC_PV_DS452_01`, `TC_PV_DS452_02`. Cần xác định điều kiện phát sinh, dữ kiện và ngoại lệ theo từng predicate. Đây là phần logic chưa bao phủ; không phải bằng chứng rằng nguồn thiếu. | Người 4; người 2–3 cung cấp facts/evidence |
| Trả chậm/trả dần | `TC_PV_DS453_02`: chưa chấp nhận được nội dung về bảo lưu sở hữu/phân bổ rủi ro. Phân biệt lịch thanh toán nhiều đợt với điều kiện pháp lý của giao dịch trả chậm/trả dần. Rà lại evidence và binding trước khi kết luận. | Người 3–4 |
| Numeric kinh phí bảo trì | `TC_PV_HYC049_02`: thiếu xác nhận `numeric_target_reviewed` cho nhánh/đơn vị/mẫu số của rule. Không tự bật cờ chỉ vì có con số 2%. | Người 4; người 1 xác nhận tri thức khi cần |
| Hai kiểm tra điều khoản cấm | `TC_PV_HYC011_01`, `TC_PV_HYC012_01`: có coverage toàn văn, nhưng chưa đủ proof vắng điều khoản cấm. Đề xuất SATISFIED trên một số đoạn không thay được proof đó. Cần rà lại phân loại trong ma trận và nội dung cụ thể. | Người 4 |
| 5 criterion trọng tài | `TC_PV_TT16_01`, `TC_PV_TT18_01`, `TC_PV_TT19_01`, `TC_PV_TT2_01`, `TC_PV_TT5_01`: C05 chưa xác định `co_thoa_thuan_trong_tai`. Kiểm tra nguồn, extraction và mapping; không suy ra CO chỉ từ việc nhắc luật trọng tài. | Người 2–3 |
| 3 yêu cầu chưa chọn được version | `FAM_GENERAL_TERMS_DISCLOSURE`, `FAM_GYC048`, `FAM_TEMPLATE_REGISTRATION` thiếu mốc `TEMPLATE_USE`. Không lấy ngày ký thay mốc dùng mẫu. Xác định đúng phạm vi, context và mốc cần bổ sung. | Người 1–3; người 5 hỗ trợ intake |
| 7 citation UNKNOWN | Cần tiếp tục định danh/chuẩn hóa theo nguồn và catalog. Không tự gán số hiệu hoặc coi UNKNOWN là VALID. | Người 3; người 1 hỗ trợ catalog |

Nhóm 7 adapter, 1 trả chậm/trả dần, 1 numeric, 2 điều khoản cấm và 5 trọng tài tạo
thành 16 C07 UNKNOWN thực sự. Ba yêu cầu thiếu version không tạo criterion theo một
version chưa được xác định, nên không cộng vào con số C07 này. C08 tổng hợp theo
requirement, vì vậy số lượng không bằng số C07 UNKNOWN.

Bằng chứng đầy đủ của lượt chạy nằm trong
`data/private/baseline_v3_fix_20261109/live_run_r5/`: summary, diagnostics, ảnh tám
tab, kiểm tra lineage, audit counts và hai file export. Thư mục private không commit.
