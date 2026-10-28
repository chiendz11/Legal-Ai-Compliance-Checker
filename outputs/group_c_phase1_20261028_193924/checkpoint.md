# Checkpoint nhóm C — giai đoạn 1

Thời điểm kiểm chứng cuối: **28/10/2026, Asia/Saigon** (giờ chính xác trong `checks.json`).
Repo: `C:\demo\Legal-Ai-Compliance-Checker`.

**Trạng thái: giai đoạn 1 đạt tiêu chí lõi và tests nghiệp vụ.**
Giai đoạn 2–3 chưa triển khai/nghiệm thu trong lượt này. Không gọi API trả phí,
không khởi tạo hoặc ghi DB, không chạy demo save/read. Đây là checkpoint tiếp tục,
chưa phải gói bàn giao toàn bộ nhóm C.

## Phần hoàn tất

- C07 giữ toàn bộ checklist đã resolve, bốn findings, quote/Unicode offsets,
  selected FINAL C06, backend review/digest, registry và xác minh độc lập.
  Bổ sung full context và contract vào snapshot mới. Decision rule thiếu ID/version,
  disabled, gate không hỗ trợ hoặc policy receipt mâu thuẫn giữ UNKNOWN.
  Local/optional exclusion không che numeric target/fact lỗi hoặc knowledge gap.
- C08 giữ thứ tự AGG_CAN_HO_V1, thiếu findings/rule/confirmation trước violation;
  giữ unresolved và chỉ loại N/A có lý do, đủ policy. Policy metadata sai dạng và
  context C07 lệch/thiếu hoặc batch trộn contracts bị từ chối. Counts/coverage/snapshot
  được kiểm thử; C07 hash/context/contract là bắt buộc.
- C10 kiểm tra hai nguồn riêng, guards, severity từ catalog, XOR nguồn và ID instance,
  context/run/pin, dedup giữ mọi rule match; thiếu C09 có diagnostic. UNKNOWN chỉ
  tạo VERIFICATION khi có policy phù hợp. Không gán hash hiện tại cho nguồn thiếu pin.
  C09 thiếu hash/context/contract có diagnostic C09_PROVENANCE_UNAVAILABLE và không
  tạo risk khẳng định STALE/INVALID; UNKNOWN còn có thể yêu cầu xác minh theo policy.
- C11 xác minh source/policy C10, bind đúng risk instance, render mọi template theo
  selection policy ALL, kiểm tra required elements/facts/limits/action/priority và
  diagnostics. Giữ evidence/legal basis/version/hash cùng metadata
  TEMPLATE_ENGINE_NO_LLM / NOT_USED / PENDING. UNKNOWN chỉ yêu cầu thông tin thiếu.
- 8 tests nối trực tiếp bốn lõi bằng dữ liệu tự dựng: bốn findings, có/không C09,
  nhánh citation không đổi C07/C08 hoặc compliance risks. Không dùng workflow.
- Kiểm kê chỉ hai sheet knowledge local: 441 criteria, 1.764 decision rules,
  7 criterion types, 12 numeric schemas; không có schema/type ngoài allowlist trong
  bản workbook này. Không đọc reference findings/observations. Hash workbook được
  ghi rõ là hash nguồn, không phải knowledge snapshot hash.

## Files sửa trong lượt này

Các đường dẫn dưới đây tương đối với repo. Nhiều files đã có sửa đổi chưa commit
từ trước; lượt này tiếp tục trên nội dung đó, không reset hoặc ghi đè công việc cũ.
`working_tree_status_after.txt` là trạng thái toàn working tree, không phải danh sách
chỉ các thay đổi của lượt này.

| Nhóm | Files |
|---|---|
| C07 | `backend/src/legal_checker/modules/compliance/criterion_reasoner.py`, `decision_rules.py` |
| C08 | `backend/src/legal_checker/modules/compliance/requirement_aggregator.py` |
| C10 | `backend/src/legal_checker/modules/risks/aggregator.py`, `citation_mapper.py`, `compliance_mapper.py`, `policy.py`, `service.py` |
| C11 | `backend/src/legal_checker/modules/recommendations/generator.py`, `validator.py`, `service.py` |
| Tests sửa | `backend/tests/unit/test_c07_hardening.py`, `test_requirement_aggregator.py` |
| Tests mới | `backend/tests/unit/test_risks.py`, `test_recommendations.py`, `test_group_c_core.py` |
| Checklist hiện có | `outputs/group_c_20261028/checklist.md` |
| Checkpoint mới | `outputs/group_c_phase1_20261028_193924/`: checklist, checkpoint, inventory/script, verification script/logs/JSON/JUnit, trạng thái working tree |

Không sửa workflow, runner, persistence, migration, JSON schemas hay README tổng thể
trong lượt này. Snapshot context là nội dung trong field dict hiện có, không thêm field
runtime contract mới.

## Lệnh và kết quả kiểm thử mới

Interpreter: `C:\demo\Legal-Ai-Compliance-Checker\.venv\Scripts\python.exe`.
Python **3.14.0**, pytest **9.1.1**. Chạy từ root repo bằng PowerShell:

```powershell
.\.venv\Scripts\python.exe -X utf8 outputs/group_c_phase1_20261028_193924/verify_phase1.py
```

Script gọi pytest với `-q -c backend/pyproject.toml` và danh sách tường minh 15 files
unit + `backend/tests/contract/test_architecture.py`; chạy Ruff check và
`ruff format --check --config backend/pyproject.toml` trên 18 files của giai đoạn 1.
**Mọi command đầy đủ và exit codes nằm trong `checks.json`.**

| Bộ kiểm tra cuối | Passed | Failed/errors | Skipped |
|---|---:|---:|---:|
| C07/grounding/numeric/provider/review/manual | 575 | 0 | 0 |
| C08 | 81 | 0 | 0 |
| C10 | 110 | 0 | 0 |
| C11 | 73 | 0 | 0 |
| Nối bốn lõi | 8 | 0 | 0 |
| Architecture | 2 | 0 | 0 |
| **Tổng pytest** | **849** | **0** | **0** |

Ruff check: **All checks passed**. Ruff format: **18 files already formatted**.
Bằng chứng: `pytest.xml`, `pytest_phase1.log`, `ruff_check_phase1.log`,
`ruff_format_phase1.log`. Chạy cuối: **849 passed in 1.21s**, ba exit codes đều 0.

Inventory:

```powershell
.\.venv\Scripts\python.exe -X utf8 outputs/group_c_phase1_20261028_193924/inventory_knowledge.py
```

Kết quả nguồn và schema cụ thể: `knowledge_inventory.json`. Lần đọc thử ban đầu
gặp encoding console Windows; đã dùng UTF-8 và xuất JSON thành công. Các ca test
hồi quy/fixtures và lỗi format phát hiện trong quá trình làm đều đã sửa và được
kiểm chứng lại trong kết quả cuối ở trên. Không có tests bị xóa hoặc thêm skip.

## Vấn đề còn lại và giới hạn

- Không còn blocker lõi được phát hiện bởi bộ tests giai đoạn 1 và rà soát chéo.
  Tests synthetic kiểm tra logic/contracts; không xác nhận tính đúng pháp lý của
  knowledge thực hoặc chất lượng upstream/LLM.
- Snapshot C07 mới giữ full context/contract; C08/C10/C11 từ chối C07 thiếu pins.
  DTO C07 legacy phải có provenance thật trước khi dùng lại, không tự gán pin mới.
  C09 có contract cũ không bắt buộc các pins bổ sung: khi thiếu sẽ diagnostic và
  chặn STALE/INVALID risks; UNKNOWN chỉ có thể tạo VERIFICATION theo policy.
  Cần ghép adapter upstream cung cấp provenance đáng tin ở giai đoạn 2.
- Selection policy C11 ngoài ALL, fact binding và policy/schema chưa hỗ trợ sẽ tạo
  diagnostics/UNKNOWN, không tự đoán. Draft/unverified và PENDING vẫn giữ nguyên.
- PostgreSQL thật, idempotency/rollback/concurrency/tampering, runner CLI và
  workflow/DI chưa chạy nghiệm thu. Không tính DB skip là hoàn thành.
- Schema drift, SQL checksum/line endings, Windows cache concurrency và ZIP
  backslash là các hạng mục được nêu trong khảo sát trước, **chưa xác nhận lại hoặc
  sửa ở lượt này**. Full pytest/Ruff toàn repo và đồng bộ tài liệu thuộc giai đoạn 3.
- Upstream OCR/Scope/Temporal/Retrieval/Citation thật và human/legal review vẫn là
  phụ thuộc ngoài phạm vi nhóm C; dữ liệu thiếu giữ uncertainty.

## Bước tiếp theo

1. Bắt đầu **giai đoạn 2** từ working tree hiện tại, giữ nguyên checkpoint này.
   Kiểm tra compliance service/workflow/DI với các snapshots và diagnostics mới;
   phân biệt compliance-only và full pipeline nhận C09.
2. Bổ sung/chạy tests runner offline/replay/flags/artifacts/export/read-run;
   mặc định không gọi API trả phí, không ghi đè artifacts cũ.
3. Dùng PostgreSQL test riêng theo prefix `legal_checker_test`; kiểm chứng save/read,
   transaction/lineage/idempotency/conflict/rollback/concurrency/history/tampering.
   Chạy demo run ID mới và chứng minh read không recompute.
4. Sang **giai đoạn 3**: checks toàn repo, đồng bộ JSON schemas và tài liệu, xử lý
   các lỗi cross-cutting có regression tests, rồi tạo gói bàn giao đầy đủ.

Chưa tuyên bố hoàn thành toàn bộ nhóm C.
