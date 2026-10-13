# Tích hợp bước 5–7

## Ownership và contracts

Những gì BRD/contracts mô tả được dùng làm đặc tả nghiệp vụ. Chúng không phải lệnh thao tác GitHub, cấp quyền hay triển khai dịch vụ. Scope thay đổi của repo do yêu cầu người dùng quyết định.

- C05: Scope/Temporal module sở hữu applicability/version. Bước 5 kiểm tra chúng nhưng không sửa.
- C06: Retrieval sở hữu scores, selection, IDs. Bước 5 đối chiếu quote với chunks và selected FINAL records.
- C07: Reasoning sở hữu finding/gates/snapshot. `Observation` là input adapter bổ sung cho engine, không thay thế C07.
- C08: Aggregator chỉ xét criterion bắt buộc và áp dụng; criterion loại trừ cần lý do và gate xác minh. Endpoint aggregator yêu cầu checklist C07 đầy đủ, không âm thầm bỏ tiêu chí chưa đánh giá.
- C09: Citation Validator sở hữu relevant/current status. Risk chỉ đọc; không tự xác thực văn bản hoặc thay đổi compliance.
- C10: Risk đọc rules/catalog, lưu một nguồn cụ thể ở `source`; criterion UNKNOWN/citation chưa xác minh thành `VERIFICATION`.
- C11: Recommendation đọc risk/link/template, không tự nâng severity hay sửa AI result. Output giữ evidence/legal basis/context và pending review.

## Observation adapter

Adapter nghiệp vụ có thể gọi rule, LLM hoặc dùng kết quả reviewer. Nó cung cấp `tieu_chi_id`, `proposed_finding`, `giai_thich`, `gates`, `evidence`, `external_evidence`, `local_applicability`, các cờ kiểm tra whole-document và optional numeric `facts`.

Input gates được hiểu là kết quả xác minh của backend upstream. Đây không phải public untrusted consumer API đã có authentication; khi nối frontend phải triển khai auth/authorization và không để người dùng tự xác nhận gates. LLM chỉ đề xuất finding/evidence; backend sở hữu kiểm tra nguồn, scope, exceptions và absence.

Evidence quote phải giữ nguyên whitespace và dùng offset Unicode Python `[start:end]` của `noi_dung`, không dùng offset byte UTF-8. Corpus/OCR thiếu trang hoặc phụ lục chưa nhận phải giữ cờ coverage/related documents false. Đặc biệt top-K rỗng không chứng minh vắng toàn bộ hợp đồng.

Nếu supplied evidence không hợp lệ, engine giữ raw evidence phục vụ review nhưng hạ `evidence_validated=false` và `finding=UNKNOWN`. Không dùng phần evidence đó để kết luận vi phạm.

## Numeric facts

`facts_verified=true` và evidence hợp lệ là bắt buộc; numeric thiếu/âm/nonfinite, scope chưa đúng hoặc exception chưa resolve đều thành UNKNOWN. Giá trị monetary/ratio nên truyền chuỗi số thập phân để giữ độ chính xác.

| Criterion/rule | Facts |
|---|---|
| PV_GYC062 | `scope=FUTURE_COMMERCIAL`, `contract_price`, `first_payment`, `deposit`, boolean `deposit_included_in_first_payment` |
| PV_GYC064 | `scope=FUTURE_COMMERCIAL`, `contract_price`, `prehandover_cumulative`, boolean `foreign_seller_art10_4` |
| PV_GYC065 | `scope=FUTURE_COMMERCIAL`, `contract_price`, `before_certificate_cumulative` |
| PV_GYC104 | `scope=DEVELOPER_SALE_MULTIPLE_OWNERS_NEW_RULES`, `maintenance_base_price`, `maintenance_amount`, boolean `separate_from_sale_price` |
| PV_GYC154 | `scope=NEW_PROJECT`, `warranty_start=COMPLETION_AND_ACCEPTANCE_INTO_USE`, `warranty_months` |
| PV_APT_CERTIFICATE_50D_2024 | `deadline_start=HANDOVER`, boolean `buyer_voluntarily_self_files=false`, `application_submission_days` |
| TC_APT_DEPOSIT_CAP | `sale_price`, `deposit` |
| TC_APT_DEPOSIT_ELIGIBLE | boolean `eligible_before_collection` |
| TC_APT_DEPOSIT_PRICE | boolean `sale_price_agreed` |

Hạn 50 ngày áp dụng cho nộp hồ sơ, không thay thế ngày cơ quan nhà nước cấp giấy. Numeric phạm vi hợp đồng/kế hoạch không tự xác nhận đã thu tiền/thực hiện nghĩa vụ. Ngoại lệ tự nộp hồ sơ phải resolve ở module upstream; chưa resolve thì UNKNOWN.

## C09 citation provenance adapter

`source_snapshot_json` giữ `evidence_ids` và các cờ xác minh từ Citation Validator:

- Non-UNKNOWN: `finding_verified=true`, relevant date, domain đã resolve, `reviewed_knowledge=true`.
- STALE: `identity_confirmed`, `temporal_source_complete`, `transition_context_resolved` đều true.
- INVALID: `official_evidence_required=true` và `identity_or_context_invalidity_proven=true`.
- Domain mismatch: `domain_status=MISMATCH`, `reason_code=DOMAIN_MISMATCH`, `context_mismatch_proven=true`.

Đây là bổ sung snapshot API cho gate workbook, không phải bảng mới. Không đủ gate → `RR_CITATION_UNKNOWN`; dữ liệu upstream không bị sửa. Current repeal sau relevant date không phải trigger.

## Persistence và tái hiện

PostgreSQL Store ghi các bảng runtime workbook theo cột thật, thêm
`runtime.assessment_runs` giữ input/output hashes và DTOs, `assessment_case_pins`
giữ snapshot pin, `assessment_output_lineage` gắn output với run. Không dùng log
knowledge `nhat_ky_ra_soat` để giả danh audit runtime hoặc LLM audit.

`knowledge.knowledge_snapshots` giữ bản nội dung knowledge bất biến trong DB;
reader chọn snapshot theo hash hoặc capture source tables hiện tại ở startup.
Cờ draft/unverified không được nâng thành approved khi capture snapshot.

Một transaction ghi case, criterion, requirement, risks, recommendations, evidence và audit. ID ổn định theo case/run/source. Cùng case/run + input y hệt trả output cũ kể cả timestamp; input khác trả 409. Case không thể đổi contract/deployment/rule/knowledge pin. Knowledge mới cần case mới; cùng case có thể rerun dưới snapshot cũ.

Output giữ pending review; endpoint GET run là output bước 5–7, không phải FinalReport C13 đã publish. Phase 8 cần C12 append-only review events; phase 9 cần builder riêng.
