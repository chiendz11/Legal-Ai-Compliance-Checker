# Checkpoint nhóm C — giai đoạn 2

**Trạng thái: giai đoạn 2 hoàn thành.** Kiểm chứng cuối lúc **01:23 ngày 29/10/2026,
Asia/Saigon**. Giai đoạn 1 được kiểm tra lại trong suite liên quan; giai đoạn 3 chưa
triển khai. Không tuyên bố hoàn thành toàn bộ nhóm C.

## Implementation và files sửa

Repo `C:\demo\Legal-Ai-Compliance-Checker`, interpreter
`C:\demo\Legal-Ai-Compliance-Checker\.venv\Scripts\python.exe` — Python 3.14.0.
Working tree vốn có nhiều sửa đổi chưa commit; lượt này tiếp tục và giữ công việc đó,
không reset, không commit hoặc tạo HTTP endpoint.

| Phần | Files sửa trong lượt này | Kết quả |
|---|---|---|
| Compliance/workflow | `backend/src/legal_checker/modules/compliance/service.py`; `backend/src/legal_checker/workflows/steps_5_7.py`, `assessment_workflow.py`, `handoffs.py` | Compliance-only riêng nhánh C07/C08/C10/C11; full pipeline nhận C09; DI draft workflow; DTO copies; xác minh C06 trước provider; thiếu upstream giữ diagnostics/UNKNOWN/NOT_RUN; registry độc lập được truyền nguyên trạng |
| Runner | `backend/src/legal_checker/modules/assessments/run_group_c.py` | Kiểm tra flags trước I/O; offline/replay/read phân biệt; Store chỉ tạo khi cần; context/lineage validation; sidecars đủ cho replay; export staging rồi publish; không ghi đè artifacts; sort JSON keys ổn định sau SQL JSONB roundtrip |
| Persistence | `backend/src/legal_checker/modules/assessments/repository.py`, `integrity.py` | Transaction normalized/full DTO/pins/lineage; exact case/run; read/retry kiểm tra checksums, membership, pins, knowledge và normalized rows, không gọi engines; C06 scores Decimal chính xác, từ chối non-finite |
| Tests | Thêm `backend/tests/unit/test_group_c_runner.py`, `test_group_c_workflow.py`; mở rộng `backend/tests/integration/test_group_c_persistence.py` | CLI 39 cases, workflow 26, persistence 43; regression lõi và các DB/handoff tests liên quan |
| Test fixture Windows | `backend/tests/conftest.py` | Đọc SQL seed bằng UTF-8 tường minh, không đổi seed hay migration |
| Evidence | `outputs/group_c_phase2_20261029_010014/`; cập nhật `outputs/group_c_20261028/checklist.md` | Scripts tái lập, input/output, normalized rows/lineage, logs/JUnit, metadata, checklist/checkpoint |

Không sửa các lõi giai đoạn 1, shared DTO models, JSON schemas, migration lịch sử
hoặc README/architecture tổng thể trong lượt này. Các file đó còn các thay đổi có
sẵn từ trước; không quy toàn bộ `git diff` cho giai đoạn 2.

## Lệnh và kết quả thực tế

```powershell
.\.venv\Scripts\python.exe -X utf8 outputs/group_c_phase2_20261029_010014/verify_phase2.py --test-database-url postgresql://legal_checker@127.0.0.1:55433/legal_checker_test_phase2
```

Script chạy pytest theo `backend/pyproject.toml` trên danh sách tường minh của 26
test files, gồm các regression lõi giai đoạn 1, runner/workflow và integration/contracts
liên quan. **Không phải full pytest/Ruff toàn repo.** Exact commands, interpreter và
exit codes nằm trong `checks.json`; stdout trong `*_phase2.log`; JUnit `pytest.xml`.

| Nhóm | Passed | Failed/errors | Skipped |
|---|---:|---:|---:|
| Các tests giai đoạn 1, gồm architecture | 849 | 0 | 0 |
| Runner CLI mới | 39 | 0 | 0 |
| Workflow mới | 26 | 0 | 0 |
| Integration/DB/handoff/snapshot/seed/package liên quan | 95 | 0 | 0 |
| **Tổng** | **1009** | **0** | **0** |

Kết quả cuối: **1009 passed in 252.73s**. Có một warning deprecation từ dependency
Starlette/httpx; không có test bị skip. Ruff check: **All checks passed**.
Ruff format --check: **14 files already formatted**. Ba exit codes đều 0.

Trong 43 persistence cases có transaction rollback/retry, concurrency một winner,
input conflict, lịch sử nhiều run/case, normalized tampering, missing/extra lineage,
rehashed foreign case/run, no-engine reads, C09 source XOR và C11 instance binding,
C06 precision/non-finite và cả SATISFIED/VIOLATED/MISSING/UNKNOWN. Các ca known dùng
synthetic trusted observations và policy applicability tường minh trong DB test;
không giả review cho chứng từ thực hoặc đổi flags phê duyệt knowledge.

## PostgreSQL và demo mới

PostgreSQL **18.4** có sẵn tại `C:\Program Files\PostgreSQL\18\bin`.
Đã khởi tạo cluster riêng `data/private/group_c_phase2_postgres/cluster`, chỉ nghe
`127.0.0.1:55433`. Tests tạo/xóa DB con `legal_checker_test_*`, không ghi DB dev.
Sandbox chặn TCP loopback; các lệnh DB đã chạy ngoài sandbox theo quyền được cấp.
**Instance đã được dừng sạch sau kiểm chứng; dữ liệu giữ nguyên.**

DB demo: `legal_checker_test_group_c_phase2_demo_36f5a9f04183`.
Nguồn: workbook local DEV_VALIDATION, case `CA360_001`, upstream run
`CA360_001_PDF360_LS2_REFERENCE`. `prepare_demo.py` chỉ đọc whitelist knowledge và
upstream C02/C05/C06; không đọc/nạp C07/C08/C10/C11 hoặc observations tham chiếu.
Trước chạy engines, cả bốn bảng kết quả đều **0 rows**. Knowledge snapshot được capture
và pin mới cho lượt đánh giá, không suy diễn việc phê duyệt từ snapshot.

- Run đạt: `CA360_001_C07_DEV_2336c2991f7544c88e216b443db8a82c`.
- Knowledge hash: `c47aa957127751775c850ea63b9ae1d0a57d6a05bfc7f65452738f243eaefdc4`.
- Input hash: `d050851b1e48309b42dcc30fe00535c7e766a03692308a088fa94ae0d6be0afb`.
- Output hash: `4ff17128b8cc9cf2f4b8eef395d5ebdb733852a1cc0f3d085728aa3577bd547b`.
- Counts: C05 **10**, selected FINAL C06 **5**, C07 **9**, C08 **10**, C09 **0**,
  C10 **9**, C11 **9**; **37 lineage rows** đúng case/run và DTO.
- C07: **9 UNKNOWN**; C08: **10 INSUFFICIENT**; C10: **9 VERIFICATION**.
  Lý do cụ thể giữ trong `diagnostics.json`, từng C07 và `demo_verification.json`:
  C05 chưa resolve đủ, C06 thiếu cho một số criterion, facts/source/scope/exceptions
  và backend review chưa xác minh. Không ép kết luận hoặc tạo review giả.
- C09 không có upstream đáng tin cho run mới nên **NOT_RUN**. Hai nhánh cùng hoạt
  động, nguồn C09 và tampering đã được kiểm chứng riêng bằng DB integration tests.
- Save/read: DTO, hashes, normalized rows và lineage khớp. Các sidecars/input/output
  save/read còn giống nhau về **bytes** nhờ JSON export xác định.
- Read: **10** điểm gọi engine/provider/Knowledge/source loader được patch để fail
  nếu gọi; **0 calls**. Không reasoning, risk hoặc recommendation được chạy lại.
- Retry cùng input: output bytes/hash cũ được trả lại; chỉ **1** run mới được thêm.
  Lịch sử từ **1 → 2** run, các input/output hashes của run cũ giữ nguyên.
- Replay dùng analyses/profile xuất từ chính lần chạy offline, không lấy output
  C07–C11 làm đáp án; chạy engines thật không save, **0 paid API attempts**.

Bằng chứng chính: `demo_verification.json`, `normalized_rows.json`, `demo_source.json`,
`demo_verified_saved/`, `demo_verified_read/`, `demo_verified_retry/`,
`demo_verified_replay/` cùng các CLI logs. Mỗi folder chứa DTO đầy đủ, hashes, counts,
snapshots, diagnostics và sidecars phù hợp.

Đã giữ artifacts lần thử đầu `demo_saved/`, `demo_read/` để truy vết phát hiện JSONB
đổi thứ tự khóa; các folder mới dùng prefix `demo_verified_`, không ghi đè lần cũ.

## Các lỗi đã xử lý trong giai đoạn 2

- Đọc SQL UTF-8 trên Windows: loại lỗi cp1258 mà không sửa seed.
- So snapshot JSONB thô với JSON text trong Knowledge adapter: thêm projection đúng
  trên bản copy, vẫn so nghiêm ngặt nội dung và giữ hash raw snapshot.
- Kiểm tra read/retry chỉ checksum DTO chưa đủ: thêm normalized rows, lineage,
  ownership và pinned knowledge; có regression tampering từng đường đọc.
- C06 float→SQL NUMERIC: dùng Decimal(str(value)), giữ precision và từ chối non-finite.
- Export dở dang và JSON key order: publish folder hoàn chỉnh và JSON xác định.
- Seed test có `criterion.dieu_kien=NULL`: giữ UNKNOWN đúng policy; ca known-status
  dùng policy synthetic tường minh trước khi capture snapshot, không nới engine.
- Chạy thử trong sandbox bị chặn network/temp: chạy lại bằng quyền ngoài sandbox;
  kết quả cuối không có skip môi trường.

## Phần còn lại và bước tiếp theo

**Giai đoạn 3 chưa triển khai.** Cần chạy toàn bộ checks theo CI, đối chiếu machine
schemas/runtime models, xử lý checksum SQL/line endings theo bằng chứng, Windows
cache concurrency và ZIP paths nếu còn lỗi, đồng bộ README/backend/modules,
architecture/hướng dẫn, rồi tạo gói bàn giao đầy đủ cuối cùng.

Nguồn upstream OCR/Scope/Temporal/Retrieval/Citation thật, xác minh chứng từ và human
legal review vẫn thuộc phụ thuộc đã nêu. Snapshot/draft/PENDING không phải phê duyệt.
Read lịch sử chỉ hỗ trợ dữ liệu đã lưu đầy đủ; legacy output thiếu lineage/provenance
bị từ chối khi không thể kiểm chứng, không ghép dữ liệu theo run mới nhất.

Xem `powershell.md` để khởi động lại instance test, đọc đúng run, chạy offline/replay
và kiểm tra lại. Khi tiếp tục giai đoạn 3, giữ working tree/checkpoint này và đọc
`checks.json`, `demo_verification.json`, `checkpoint.json` trước khi sửa.
