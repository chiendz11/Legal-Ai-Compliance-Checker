# Rà soát và thống nhất tài liệu cho năm người — 07/11/2026

## 1. Kết quả và phạm vi

Đối chiếu docs với manifest TEAM, Protocols, composition, repositories, migrations,
HTTP models và frontend client trong working tree feat/integration-contract-alignment.
Không suy tiến độ cá nhân từ tác giả commit. Đây là thay đổi đặc tả, OpenAPI/types và
kiểm tra drift; không triển khai verifier/OCR mới hoặc chạy inference để tạo nhãn.

Các quyết định bên dưới đã chốt, không yêu cầu năm người tự chọn lại. Tài liệu chung
là [INTEGRATION_V1](../contracts/integration_spec.md),
[playbook](parallel_development_playbook.md),
[catalog](../contracts/catalog.json), [dictionary](../contracts/data_dictionary.md)
và [guide dataset](dataset_team_baseline_20261107.md).

## 2. Những mâu thuẫn tìm được và quyết định sửa

| ID | Trước khi rà soát | Quyết định thống nhất | Người liên quan |
|---|---|---|---|
| D01 | Guide mới pin TEAM nhưng module README vẫn hướng dẫn reviewed 05/11, 10 families và update tại chỗ | TEAM_BASELINE_20261107, scope reference 36 atomic requirements; live full catalog 323 families; DB mới và giữ DB cũ | 1 phát hành; 2–5 kiểm pin |
| D02 | Ví dụ SQL/Python hardcode CA360_001_PDF360_LS2_REFERENCE, không còn là run của release mới | Ví dụ mới REF_TEAM_20261107_CA360_001; thực tế chọn từ QA/context, bind exact case/run/hash, không lấy MAX(run_id) | 2–5 |
| D03 | Nhóm A vừa được giao C01 vừa được yêu cầu viết lại upload/use case dù API đã có | 5 sở hữu route/upload/case; 2 sở hữu source validation/extraction/writer; 1 shared storage/schema | 1, 2, 5 |
| D04 | Các bước mô tả mọi module phải ghi normalized tables, trong khi live workflow truyền DTO | Live dùng DTO/memory và workflow_runs.draft_json; Documents persist trước Retrieval; normalized recipes cho baseline/standalone | 2 writer; 3/4 consumers; 5 composition |
| D05 | Bảng D1/Q46 đọc bao_cao_danh_gia như report live | Report live đọc report_versions exact case/run/version; report_json chứa FinalReport envelope, content nằm thêm một cấp report_json; exports_json giữ exports | 5 |
| D06 | Q45 dùng nhat_ky_review làm nguồn/thứ tự review | review_events chọn case/run, ORDER BY seq; mirror không là nguồn quyết định revision; service kiểm target hash và quyền | 5 |
| D07 | Catalog ghi C08 là input executable RiskRequest và ghi publishing chưa implement | RiskRequest dùng C05/C07/C09; C08 dành aggregation/report. Review/publication đã có use cases, builder chỉ dựng draft | 4, 5 |
| D08 | Envelope schema bị hiểu như chữ ký hàm; chưa có danh mục port/caller | Catalog ghi runtime_port/call_parameters/owner/composition_owner; test đối chiếu với Python Protocol/function thực | 2–5 |
| D09 | Recipe yêu cầu verifier lấy selected C06/registry nhưng verify không nhận hai argument đó | Verifier kiểm profile facts/evidence/active chunks/coverage. ObservationProvider kiểm C06. Chứng từ dùng dependency read-only inject qua constructor, cùng evidence IDs/SHA với registry | 4 implement; 5 inject; 2 nguồn |
| D10 | Job complete, nhãn pháp lý, review và retry dễ bị coi là cùng trạng thái | Tách run/stage/C07-C08/diagnostic/review. Chưa có criterion resume; provider retry, queue recovery và explicit new run là ba cơ chế riêng | 4, 5; 1 queue |
| D11 | SOURCE_CHECKED có thể bị hiểu là đã mở mọi gate của C07/C09/C10 | Không tự promote. C07 kiểm flags cụ thể; C09 reviewed_knowledge hiện cần HUMAN_VERIFIED snapshot; C10 có thể trả CITATION_PRODUCTION_GATE dù C09 có status | 1 dữ liệu; 3/4 engines; 5 UI |
| D12 | OpenAPI thiếu PipelineResult.diagnostics và Bearer ghi chưa implement | Đồng bộ HTTP schema graph với models hiện tại, giữ operationId/auth/error semantics và aliases frontend đang import; sinh lại schema.d.ts | 5; 1 hỗ trợ checks |
| D13 | DOCX/OCR được mô tả như input/parser đã hỗ trợ; demo có câu fallback reference không phân biệt mode | PDF text là capability hiện tại. Scan/DOCX báo rõ chưa hỗ trợ; modules không fallback QA, modules_di_reference/reference chỉ DEV/EVAL | 2, 5 |
| D14 | Review/update guide và trạng thái theo tuần có thể bị đọc là hiện trạng sản phẩm | Đánh dấu tài liệu reviewed-flags là lịch sử; BRD/contracts gốc/PDF/slides/kế hoạch không thay live schemas/manifest/acceptance. Không sửa phần trăm hoàn thành hoặc binary nguồn để giả nghiệm thu | 1 điều phối; cả nhóm |

Không thay bytes/URL/chunks của 360 PDF hoặc tạo release dataset khác trong lượt sửa
docs này. Workbook, ZIP và manifest content hashes giữ baseline đã chốt trước đó.

## 3. Nối một lần chạy thật như thế nào?

```text
P5 API upload/case → C01 + source SHA/deployment/tenant
  → P2 Documents đọc bytes thật → C02 + chunks + C03 + coverage
  → composition commit DocumentRepository một lần
  → P3 Scope(C02, knowledge) → C04
  → P3 Temporal(C02, C04, knowledge) → C05
  → P3 Retrieval(C05, active chunks, knowledge) → C06
  → P4 verifier(C02, C05, active chunks, coverage) → kiểm facts/nguồn
  → ObservationProvider(C05,C06,...) → đề xuất + grounding/checks
  → P3 Citation(C02,C03,knowledge) → C09
  → P4 steps_5_7.evaluate → C07/C08 + merged C10/C11
  → P5 C13 draft + workflow completion cùng transaction
  → C12 review riêng → version mới → publish/export theo revision/quyền
```

Đây là thứ tự implementation hiện tại, không phải hai Celery pipelines chạy song
song. Việc năm người dev song song nhờ upstream tham chiếu không đòi execution của
các module cũng chạy đồng thời. Các nhánh vẫn độc lập về nghiệp vụ: C09 không đổi
checklist hoặc nhãn compliance; chúng hội tụ ở risk/report.

Ví dụ người 4 test riêng Reasoning: dùng C05/C06/chunks làm upstream, tạo observations
thật của mình; C07/C08 tham chiếu chỉ dùng đối chiếu sau chạy. Khi người 5 ghép live,
đổi upstream mẫu bằng DTO thực, giữ schema/IDs/pins; không JOIN C07 seed bù kết quả
thiếu. Risk-only được dùng C07/C09 reference làm input, khác Reasoning-only.

## 4. Ai cần bàn giao gì tiếp?

| Người | Việc đã có quy định rõ | Implementation/nghiệm thu cần cung cấp |
|---|---|---|
| 1 | Dataset pin/review/scope/topic mapping, schema và release policy | Publish code/ZIP đúng bytes; reproducible setup, release/backup/restore; annotation độc lập nếu công bố quality |
| 2 | FULL90 có 19 trường literal; CORE/TARGETED/conditional facts, raw spans/units/unknown/coverage | Extraction thực đủ nguồn; OCR/DOCX chỉ khi mở capability; eval trên DEV/VAL, giữ missing/conflict; writer idempotent |
| 3 | Typed scope/marker policy, atomic families, C06 ownership và C09 provenance | Eval Scope/Temporal/Citation/Retrieval trên đúng scope; hỗ trợ source/name-only/transition theo policy; không dùng output reference làm relevance gold |
| 4 | Signature verifier/registry, recipe criterion types, Decimal/targets/absence/performance và C07–C11 | Verifier nghiệp vụ có implementation và source checks; bảng criterion IDs/predicates/units/targets được hỗ trợ; tests cho nhánh đúng/thiếu/vi phạm; quality độc lập |
| 5 | Factory/DTO composition, persistence authority, status/retry/review/report/OpenAPI | Inject verifier/registry vào cả API và worker; E2E thật, quyền/tenant/recovery; UI phân biệt diagnostic và nhãn pháp lý; nghiệm thu review/export |

Bảng criterion bindings người 4 bàn giao cùng PR phải nêu criterion/version, predicate,
facts/units/source, evaluation target, verifier implementation, trường hợp UNKNOWN,
tests/ca đối chiếu. Numeric dictionary là superset có điều kiện, không có nghĩa mọi
criterion cần toàn bộ fields. Semantic prose trong catalog không tự là một predicate
đã implement. Ngoài capability đã khai báo giữ UNKNOWN/diagnostic, không âm thầm
thu nhỏ checklist hoặc giả đã support toàn bộ 479 criteria.

Đây là công việc code/chất lượng còn lại sau khi chốt đặc tả, không phải để năm người
tự suy luận lại contract. Không kết luận ai đã hoàn thành task cá nhân nếu thiếu bằng
chứng; handoff phải có producer thật → consumer thật và source/pins phù hợp.

## 5. Bộ kiểm tra chống lệch tài liệu

Đã bổ sung test_team_delivery_baseline.py để kiểm:

1. Manifest/dictionary/policy/catalog/acceptance cùng baseline/hash/scope/review.
2. Port đã ghi tồn tại và đúng tên/thứ tự tham số; coverage keyword-only; Risk không
   yêu cầu một C08 field mà DTO không có.
3. Models OpenAPI và aliases FE đồng bộ runtime, gồm diagnostics.
4. EXPLAIN các SELECT recipes trên PostgreSQL riêng đã chạy migrations: phát hiện
   bảng/cột cũ, JOIN mơ hồ hoặc cú pháp sai, không query DB khách hàng.

Các tests contract khác kiểm JSON Schema, OpenAPI, links/anchors và các handoff
semantics đã có. Frontend phải gen:api và build sau đổi HTTP spec. SQL compile/schema
pass không đo relevance, facts extraction, LLM hay tính đúng pháp lý của toàn corpus.

Kết quả đã chạy trong lượt này:

- Toàn bộ backend/tests/contract: **64 passed**, PostgreSQL tests được bật, không
  bỏ qua nhóm SQL vì thiếu DB.
- **46 SELECT recipes** trên bảy tài liệu biên dịch thành công qua EXPLAIN trên DB
  tạm đã migrate; không query dữ liệu khách hàng.
- Sau khi thêm kiểm tra bảo toàn alias và chỉnh wording cuối, chạy lại hai file
  team_delivery_baseline/integration_alignment: **17 passed**; đây là subset của
  suite trên, không cộng thành 81 tests độc lập.
- Frontend gen:api, TypeScript và Vite build: **pass**. Lần đồng bộ đầu đã bỏ sót
  alias type mà client import; đã giữ lại các alias đó và thêm regression check.
- Ruff trên test mới và git diff --check: **pass**.

PostgreSQL qualification là container riêng; sau kiểm tra được tắt và xóa. K3d/DB
dev/dataset không được cập nhật bởi lượt này. Không coi scenarios trong
handoff_acceptance.json là bằng chứng đã nghiệm thu trên provider/PDF thật; lượt
này không gọi LLM, chạy full inference hoặc xác nhận quality của 479 criteria.

## 6. Cách dùng tài liệu từ nay

Đọc README docs → playbook → guide dataset và integration_spec → dictionary/catalog →
guide nhóm. Mỗi PR dùng acceptance matrix theo mức test/qualification; C12 human
review, legal gold, source integrity và knowledge review là những lớp khác nhau.

Bổ sung gate tech lead tại mục 14 của playbook: freeze canonical fact names/aliases,
không đóng handoff chỉ bằng schema/Protocol tests, bắt buộc producer thật → consumer
thật và E2E trước khi chốt tích hợp. Onboarding cũng phân biệt điểm nối Documents/
C09 đã có với verifier nghiệp vụ và nghiệm thu còn lại.

Khi sửa field/signature phải cập nhật schemas/catalog/producer/consumer/tests cùng
PR; HTTP đổi thêm OpenAPI + generated FE types, DB đổi bằng Alembic, dataset đổi pin
và strategy riêng. Không sửa nguồn lịch sử dưới một hash cũ. Lượt này không commit/
push/deploy, không bật k3d hoặc cập nhật DB dev; PostgreSQL tạm chỉ dành kiểm tra SQL.
