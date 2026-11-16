# Rà soát và thay đổi nền tảng tích hợp năm người — 05/11/2026

Nhánh: `feat/integration-contract-alignment`, xuất phát từ main `888be9d`.
Đây là bản ghi các thay đổi thực hiện sau rà soát contracts, code, SQL migrations,
FE và snapshot knowledge reviewed. Không dựa trên tác giả commit để đánh giá cá nhân.

Bổ sung revision tri thức 06/11: xem [báo cáo thay đổi tri thức](knowledge_alignment_changes_20261106.md). Số liệu gap trong phần rà soát 05/11 bên dưới là lịch sử, không phải kết quả của revision mới.

## 1. Phương án đã chốt

Giữ modular monolith, truyền DTO bằng Python; API/worker dùng chung backend image.
Chốt INTEGRATION_V1 làm đặc tả hiện hành, dictionary cho canonical fields/units và
H01–H24 cho ownership/điều kiện bàn giao. Không tạo microservices hoặc endpoint cho
mỗi bước. Không chuyển thiếu dữ liệu thành verified/COMPLIANT để làm đẹp kết quả.

Thực hiện theo thứ tự: sửa tài liệu hiện trạng/liên kết → dictionary và inventory
→ scope/temporal/verification policy → handoff guards và điểm nối → DB/FE/review
→ runbook/release → checks. Các tài liệu lịch sử giữ nhưng chỉ rõ baseline.

## 2. Bằng chứng rà soát và giới hạn

Snapshot hash `df6ed7aa9f5100bfe68430b950d55542db752e7255c324e18be171ce0d0d3ade`.
Tool mới chỉ SELECT snapshot tồn tại và kiểm hash; không capture snapshot mới hoặc
sửa DB. Inventory đầy đủ một hàng mỗi criterion được lưu ngoài Git:
`data/private/integration_audit_20261105/criterion_fact_matrix.csv` và JSON cùng folder.

| Phạm vi kiểm | Kết quả |
|---|---|
| Knowledge inventory | 441 criterion, 306 families |
| Scope chưa typed mapping | 14 records: 9 la_giao_dich_dien_tu, 5 can_danh_gia_trong_tai |
| Marker chưa có policy phân giải | 81 families toàn catalog; con số 80 trước đây thuộc một run |
| Direct article/primary document ownership | 2 criterion cần người 1/3/4 xác nhận mapping hay multi-source |
| Numeric fact candidate groups | 14 criterion; nhánh/target còn cần review binding |
| Semantic predicate/evidence | 427 criterion; không suy diễn tự động thành gold fact mapping |
| HTTP | 26 method/path có handler; schema records hiện khớp Python models |
| Docs links | Kiểm cả đường dẫn và heading anchors; sửa các link vỡ sau khi tách folder |

Inventory là độ phủ metadata, không phải chứng nhận pháp lý/OCR/evidence relevance.
Đã kiểm các đường nối của năm người; chưa chạy eval toàn bộ 360 PDF hoặc provider
thật trong thay đổi này. Các schema/model existing và live behavior được phân biệt.

## 3. Tài liệu và contracts thay đổi

- `docs/contracts/integration_spec.md`: nguồn có thẩm quyền, H01–H24, execution modes,
  checklist/temporal, verification, C09 pins, persistence, FE/review và nghiệm thu.
- `data_dictionary.json` + `.md`: toàn bộ ProfileFields, canonical numeric facts và
  units/review references, alias không tự động, marker semantics, owner và field gaps.
- `integration_policy.json`: machine-readable modes, review policy, action taxonomy,
  nguồn chuẩn và các trục release/version.
- `citation_provenance.schema.json` + model CitationProvenance: required live pins.
- `catalog.json`: bỏ nhãn skeleton chung không còn đúng; link normative spec và gaps.
- `database_catalog.json`: giữ 56 baseline tables, bổ sung inventory 11 bảng vận hành
  từ migrations. Không giả đây là schema đầy đủ thay Alembic.
- OpenAPI: metadata cập nhật 26 handlers/auth; giữ operationIds và schemas HTTP.
- Kiến trúc, guides A–D, dataset/startup/DevOps/onboarding và các link đã di chuyển.

Contracts C01–C13 lịch sử vẫn đọc được; không thay schema workbook hoặc bytes PDF.
C09 legacy dict không bị bắt phải có pins mới khi đọc lịch sử, nhưng không tự trở
thành live finding đủ provenance. Thay đổi model field khác phải cập nhật schema
và consumer trong cùng PR theo test conformance đang có.

## 4. Các điểm nối code được sửa

| Trước | Sau | Owner/task liên quan |
|---|---|---|
| modules có thể dùng QA khi remote PDF chưa có cache | modules đọc bytes thật qua storage; QA chỉ khi explicit modules_di_reference/reference | 2+5; 1 storage |
| Extraction trả DTO nhưng chưa persist metadata | DocumentRepository.save trước consumer; active chunk IDs lọc section paths/fact evidence | 2+3+5 |
| Verifications chưa có điểm cấu hình chung | Protocol CriterionVerificationProvider và EvidenceRegistryProvider; injection build_services/source, kiểm pin và gọi trước C07 | 4 implement; 5 nối |
| Thiếu verifier không rõ lý do | VERIFICATION_PROVIDER_NOT_CONFIGURED được ghi vào diagnostics/report | 4+5 |
| C07 nhánh không xử lý xóa scope/version flags đã biết | Giữ upstream scope/version; không bật gate facts/nguồn/absence còn thiếu | 3+4+5 |
| C09 thiếu hash/context/contract | Producer dựng/validate CitationProvenance; C10 kiểm pins như trước | 3+4 |
| C09 domain UNKNOWN có thể thành VALID | Giữ UNKNOWN; identity message không phủ nhận năm đã trích được | 3 |
| review snapshot bị lẫn với review finding | Hai cờ reviewed_knowledge/finding_checks_verified độc lập | 1+3+5 |
| C13 chỉ có context/module_source | Giữ run diagnostics, policy ID và danh sách checklist thực tế | 5; 3+4 codes |
| COMPLETED ghi trước report riêng transaction | Cùng transaction report đầu tiên + run completion, lỗi rollback cả hai | 5 |
| Publish có thể bỏ qua các UNKNOWN chưa review | REVIEW_ALL_FINDINGS_V1: mọi target có CONFIRM/OVERRIDE, COMMENT không đủ | 5; reviewer |
| FE đếm mọi requirement là trong phạm vi | Đếm được xét/xác nhận áp dụng/không áp dụng; version chưa resolved ghi ứng viên | 3+5 |
| VERIFY_REFERENCE nằm trong corrective | Taxonomy xác minh đồng bộ; Audit hiển thị diagnostics/profile | 4+5 |

Verifier injection không có nghĩa đã implement mọi phép kiểm nghiệp vụ. Không có
verifier hoặc attestation phù hợp vẫn UNKNOWN. Đường code cho người 4 được mô tả
bằng Protocol và ví dụ composition; không tạo auto-human-verification.

Run đã có/report đã xuất vẫn giữ snapshot cũ. Không chạy lại inference hoặc rewrite
history. Source selection và review policy mới áp dụng khi chạy code nhánh mới;
không đồng nghĩa cụm k3d hiện tại đã nhận image này.

## 5. Còn phải làm theo từng người

| Người | Phần đã chuẩn hóa để tiếp tục | Công việc nghiệp vụ/nghiệm thu còn lại |
|---|---|---|
| 1 | Dataset pins, inventory, catalog/DB authorities và release quy trình | Review 81 marker families, coverage/overlap và 2 source links với 3/4; phát hành dataset mới khi đổi nội dung; backup/restore |
| 2 | Source thật, writer trước consumer, active extraction, vocabulary | Extraction social/electronic/status/facts; warranty đã có ở PDF nhưng bị bỏ sót; OCR/DOCX theo phạm vi; citation occurrence accuracy |
| 3 | C09 provenance/domain, temporal uncertainty và checklist denominator rõ | Mapping scope/catalog, lịch sử/overlap, identity tên+năm policy, 5 retrieval misses đã quan sát và metrics |
| 4 | Verifier port đã nối, canonical facts/units và backend gates rõ | Implement criterion-bound verifier, numeric branch/target binding, kiểm quote/predicate/ngoại lệ, giảm provider/budget failures; message kỹ thuật khác thiếu hồ sơ |
| 5 | Điểm nối extraction/verifier, report/transaction, FE labels và review gate | Cấu hình provider thật từ người 4, E2E nhiều tài liệu, auth/tenant/recovery/export, nghiệm thu customer release |

Không suy ra phần trăm hoàn thành từ bảng này. UNKNOWN do tài liệu thiếu vẫn là
output hợp lệ; UNKNOWN vì field chưa hỗ trợ phải được nhận diện là giới hạn hệ thống.

## 6. Mỗi người lấy thay đổi và kiểm tra

Khi nhánh đã review/merge mới lấy từ main; hiện không tự push/merge/deploy.
Giữ DB/workbook cũ của mình và phần code đang phát triển. Nhánh không đổi migration,
workbook/PDF hoặc manifest checksum; không cần seed lại chỉ vì gói alignment này.

```bash
source .venv/bin/activate
python -m pip install -e './backend[dev,dataset]' -c constraints.txt
python -m scripts.local_db check
python -m devtools.integration_audit --output data/private/integration_audit
pytest -q -c backend/pyproject.toml backend/tests/contract
npm --prefix frontend run gen:api
npm --prefix frontend run build
```

Restart API/worker sau khi đổi code/config. Giữ ASSESSMENT_MODULES=modules cho PDF
thật; muốn DI fixtures phải chọn modules_di_reference. Chưa cung cấp provider hoặc
LLM offline thì không kỳ vọng mọi criterion có nhãn rõ. Publish sẽ yêu cầu review
quyết định cho mọi target; không dùng COMMENT như phê duyệt.

## 7. Phát hành dữ liệu và triển khai

Đổi PDF/catalog thực chất phải phát hành revision mới và giữ source/hash/annotations
đi cùng nhau. Đổi flags reviewed không bổ sung được giá trị null hoặc policy thiếu.
Dataset pull chỉ tải; Alembic init nâng schema; seed DB mới; update có kiểm soát cho
DB cũ. Updater reviewed không tự giải quyết xóa business rows/rechunk toàn corpus.

Image publication, GitOps targetRevision, Argo rollout và DB update là các bước độc
lập. Chưa rollout không nói UI local đã có sửa mới. Môi trường phase-two theo nhánh
GitOps feature; không tự merge/chuyển nhánh hai repo khác trong thay đổi này.

## 8. Kết quả kiểm tra

Đã chạy local trên Python 3.14, PostgreSQL test DB tách riêng và Node/Vite:

| Kiểm tra | Kết quả |
|---|---|
| Backend toàn bộ suite | **1.447 passed, 7 skipped**, 107,82 giây; một deprecation warning thư viện TestClient |
| Ruff lint | Pass |
| Ruff format check | 330 Python files pass |
| Frontend gen:api + TypeScript + Vite build | Pass |
| Contract/schema + docs links/anchors | Pass trong suite |
| Git whitespace diff | Pass |
| Inventory snapshot thực tế | 441 dòng CSV, pin/hash hợp lệ; read-only |

Regression mới kiểm provenance hash/context, domain UNKNOWN, source thật không QA
fallback, extraction đã lưu trước consumer, injection verifier, registry ngoại run,
report/completion rollback nguyên tử, review UNKNOWN/COMMENT và taxonomy FE–BE.

Log test và inventory ở data/private/integration_audit_20261105 ngoài Git. Không gọi
LLM mới, không eval lại 360 PDF, không push/chạy CI hoặc rollout cluster trong gói
thay đổi này. Không thay workbook, PDF, DB ứng dụng, migration hoặc manifest checksum.
7 skip được giữ nguyên trong kết quả, không coi là đã chạy thành công.

Phân biệt local tests, CI, provider thật, corpus evaluation và deployment; không
đánh đồng các mức này hoặc coi gói alignment là chứng nhận release khách hàng.

## 9. Bổ sung TEAM_BASELINE_20261106

Lần rà soát tiếp theo theo yêu cầu docs đủ cụ thể để năm người làm song song:

- Thêm parallel_development_playbook.md: nguồn chuẩn, phạm vi capability, RACI,
  input độc lập, gói bàn giao từng người, primitive mapping, quy trình pair và DoD.
- Thêm criterion_verification_guide.md cho bảy loại criterion và numeric branches.
  Dictionary bổ sung evaluation_target, condition_triggered, optional_choice_confirmed;
  schema CriterionVerification và DocumentReadCoverage riêng cho coding.
- Phát hiện verifier trước đó chưa nhận thông tin trang không đọc được. Port verify
  nay nhận keyword coverage từ đúng extraction; QA không có metadata thật thì None.
  Coverage chỉ nói khả năng đọc text layer, không tự xác nhận đủ phụ lục hoặc absence.
  Người đã viết provider theo port cũ cần nhận keyword coverage; C01–C13 payloads
  lịch sử không thêm field này và không đổi contract_version serialized.
- Sửa source URL-only: object_uri có thể null theo C01, kiểm local bytes không được
  gọi startswith trên None. Bổ sung regression cho case hợp lệ này.
- Thêm handoff_acceptance.json gồm 19 scenarios, owners, expected behavior, test nodes
  đang có và evidence cho qualification thật. Tài liệu này là requirements, không
  phải báo cáo 19 scenario đã chạy/pass; bốn qualification scenarios cần actual runs.
- Catalog bổ sung consumers thực của C02/C05 và review targets; phân biệt output
  compliance-only với merged PipelineResponse.
- Thay các hướng dẫn live persistence còn cũ bằng workflow_runs/report_versions/
  review_events; standalone Store/lineage và QA/normalized baseline được phân biệt rõ.
- Đối chiếu W3C PROV, Pact provider verification, Docling, LegalBench-RAG và NIST;
  engineering_references.md nêu phạm vi áp dụng. Không cài framework/dịch vụ mới.
- Sửa mô tả số numeric: code có 8 kinds/10 accepted shapes gồm legacy, không phải 12.

Mốc test 1.447 pass ở mục 8 thuộc gói ngày 05/11. Kết quả riêng ngày 06/11:

- Backend toàn bộ suite: **1.454 passed, 7 skipped**, 102,29 giây; TestClient có một
  deprecation warning thư viện như lần trước.
- PostgreSQL test tạm: 17.11, Docker cached image postgres:17 với --pull=never;
  khác tag pin CI 17.10, không gọi lần chạy này là CI. Container/DB test đã được dọn.
- Contract/metadata targeted suite: **36 passed**; kiểm coverage DTO, semantic controls,
  bảy criterion types, schema đồng bộ và test references trong acceptance matrix.
- Ruff lint/format và git whitespace diff: pass.
- Log/environment ở data/private/integration_audit_20261106 ngoài Git.

Không chạy provider thật, không chứng nhận bốn qualification scenarios đã pass.
Không bật Legal cluster, seed/update DB ứng dụng, thay workbook/PDF hoặc rollout.
Nhánh vẫn feat/integration-contract-alignment, chưa commit/push. Các data/domain
blockers còn lại đã có owner/expected deliverable, chưa được gán là resolved.
